-- The FOCUS 1.2 warehouse.
--
-- Two decisions carry the whole cost model:
--
--   PARTITION BY DATE(ChargePeriodStart)
--       Every dashboard scopes to a period. Without the partition, a query for
--       "last month" reads two years. This is the difference between a $5/month
--       BigQuery bill and a $500 one.
--
--   CLUSTER BY ProviderName, ServiceCategory, tag_application
--       The three columns the filter row actually filters on, in descending
--       order of selectivity. Clustering prunes blocks within a partition.
--
-- Column names and types come straight from `finops_core.focus.SCHEMA`, so a
-- FOCUS export from AWS Data Exports, Azure `FocusCost` or the GCP
-- `gcp_billing_export_focus_*` table loads without a mapping step.
--
-- `Tags` is stored as a JSON STRING, not a STRUCT. The spec calls it a map
-- "rendered as String or JSON depending on the emitter" -- both conformant --
-- and a string survives the fact that two vendors will not agree on the key set.
-- The six canonical `tag_*` columns are materialised on ingest so the filter row
-- and the clustering key have something typed to bite on.

CREATE SCHEMA IF NOT EXISTS `${PROJECT}.${DATASET}`
OPTIONS (location = '${LOCATION}');

CREATE TABLE IF NOT EXISTS `${PROJECT}.${DATASET}.focus_costs`
(
  -- Billing account & period ------------------------------------------------
  BillingAccountId        STRING    NOT NULL,
  BillingAccountName      STRING    NOT NULL,
  BillingAccountType      STRING,
  BillingCurrency         STRING    NOT NULL,
  BillingPeriodStart      TIMESTAMP NOT NULL,
  BillingPeriodEnd        TIMESTAMP NOT NULL,
  InvoiceId               STRING,
  InvoiceIssuerName       STRING    NOT NULL,
  SubAccountId            STRING,
  SubAccountName          STRING,
  SubAccountType          STRING,

  -- Charge classification ---------------------------------------------------
  ChargeCategory          STRING    NOT NULL,   -- Usage|Purchase|Tax|Credit|Adjustment
  ChargeClass             STRING,               -- nullable; only 'Correction'
  ChargeDescription       STRING    NOT NULL,
  ChargeFrequency         STRING,
  ChargePeriodStart       TIMESTAMP NOT NULL,   -- the partition key
  ChargePeriodEnd         TIMESTAMP NOT NULL,

  -- Costs -------------------------------------------------------------------
  BilledCost              NUMERIC   NOT NULL,
  EffectiveCost           NUMERIC   NOT NULL,   -- amortised; every executive KPI
  ListCost                NUMERIC   NOT NULL,   -- on-demand-equivalent; the ESR denominator
  ContractedCost          NUMERIC   NOT NULL,
  ContractedUnitPrice     NUMERIC,
  ListUnitPrice           NUMERIC,

  -- Pricing -----------------------------------------------------------------
  PricingCategory         STRING,               -- Standard|Dynamic|Committed|Other
  PricingCurrency         STRING,
  PricingQuantity         NUMERIC,
  PricingUnit             STRING,
  -- FOCUS 1.2 added these three. They are Conditional, not optional: a payer
  -- that bills in anything other than the billing currency (an Azure EA priced
  -- in EUR, say) carries its native-currency prices here, and dropping them
  -- silently loses the only record of what was actually quoted.
  PricingCurrencyContractedUnitPrice NUMERIC,
  PricingCurrencyEffectiveCost       NUMERIC,
  PricingCurrencyListUnitPrice       NUMERIC,

  ConsumedQuantity        NUMERIC,              -- 0 with EffectiveCost>0 == idle
  ConsumedUnit            STRING,

  -- Commitment discounts (RI / Savings Plans / CUDs) -------------------------
  CommitmentDiscountCategory STRING,            -- Spend|Usage
  CommitmentDiscountId       STRING,
  CommitmentDiscountName     STRING,
  CommitmentDiscountQuantity NUMERIC,
  CommitmentDiscountStatus   STRING,            -- Used|Unused  <- commitment waste
  CommitmentDiscountType     STRING,
  CommitmentDiscountUnit     STRING,

  CapacityReservationId      STRING,
  CapacityReservationStatus  STRING,

  -- Provider / service -------------------------------------------------------
  ProviderName            STRING    NOT NULL,   -- cluster key 1
  PublisherName           STRING,
  ServiceCategory         STRING    NOT NULL,   -- cluster key 2
  ServiceName             STRING    NOT NULL,
  ServiceSubcategory      STRING,

  -- Resource -----------------------------------------------------------------
  ResourceId              STRING,
  ResourceName            STRING,
  ResourceType            STRING,
  RegionId                STRING,
  RegionName              STRING,
  AvailabilityZone        STRING,

  -- SKU -----------------------------------------------------------------------
  SkuId                   STRING,
  SkuMeter                STRING,
  SkuPriceDetails         STRING,
  SkuPriceId              STRING,

  -- Metadata --------------------------------------------------------------------
  Tags                    STRING,               -- JSON object, as a string

  -- Canonical allocation tags, materialised on ingest ---------------------------
  tag_application         STRING    NOT NULL,   -- cluster key 3; 'Unallocated' when absent
  tag_business_unit       STRING    NOT NULL,
  tag_cost_center         STRING    NOT NULL,
  tag_environment         STRING    NOT NULL,
  tag_owner               STRING    NOT NULL,
  tag_project             STRING    NOT NULL,

  -- Provenance -------------------------------------------------------------------
  _ingested_at            TIMESTAMP NOT NULL,
  _binding                STRING                -- which payer / tenant this came from
)
PARTITION BY DATE(ChargePeriodStart)
CLUSTER BY ProviderName, ServiceCategory, tag_application
OPTIONS (
  description = 'FOCUS 1.2 Cost and Usage. One row per charge. See finops_core.focus.',
  require_partition_filter = TRUE   -- a query without a period filter FAILS rather than scans everything
);


-- The nightly optimization snapshot.
--
-- The 12 row-level detectors in `finops_core.engines.optimize` scan resource ids
-- and SKU strings. Running them per request would scan the whole table on every
-- dashboard load, and their answer changes at most once a day. A Cloud Run Job
-- materialises this table; the API reads it.

CREATE TABLE IF NOT EXISTS `${PROJECT}.${DATASET}.opportunities`
(
  as_of              DATE      NOT NULL,
  lever_id           STRING    NOT NULL,
  lever_name         STRING    NOT NULL,
  category           STRING    NOT NULL,   -- Rate|Usage|Architecture|AI/GPU
  cloud              STRING    NOT NULL,
  scope              STRING,
  monthly_savings    NUMERIC   NOT NULL,
  annual_savings     NUMERIC   NOT NULL,
  effort             STRING,
  risk               STRING,
  time_to_value      STRING,
  confidence         FLOAT64,              -- lowered where the bill cannot prove the claim
  evidence           STRING,               -- JSON
  resource_count     INT64,
  _generated_at      TIMESTAMP NOT NULL
)
PARTITION BY as_of
CLUSTER BY category, cloud
OPTIONS (description = 'Nightly optimization snapshot. Read the MAX(as_of) partition.');
