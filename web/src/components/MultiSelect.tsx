import { useEffect, useMemo, useRef, useState } from "react";

interface Props {
  label: string;
  options: string[];
  selected: string[];
  onChange: (values: string[]) => void;
}

/** A compact multi-select for the filter row. Selecting nothing means "all". */
export function MultiSelect({ label, options, selected, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const summary = useMemo(() => {
    if (!selected.length) return "All";
    if (selected.length === 1) return selected[0];
    return `${selected.length} selected`;
  }, [selected]);

  function toggle(v: string) {
    onChange(selected.includes(v) ? selected.filter((x) => x !== v) : [...selected, v]);
  }

  return (
    <div className="ms" ref={ref}>
      <button
        className={`ms-trigger${selected.length ? " has-value" : ""}`}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className="ms-label">{label}</span>
        <span className="ms-summary">{summary}</span>
        <span className="ms-caret" aria-hidden>
          ▾
        </span>
      </button>
      {open && (
        <div className="ms-menu" role="listbox">
          {selected.length > 0 && (
            <button className="ms-clear" onClick={() => onChange([])}>
              Clear
            </button>
          )}
          {options.map((o) => (
            <label key={o} className="ms-opt">
              <input type="checkbox" checked={selected.includes(o)} onChange={() => toggle(o)} />
              <span>{o}</span>
            </label>
          ))}
          {!options.length && <div className="ms-empty">No values</div>}
        </div>
      )}
    </div>
  );
}
