import { useId, useState, type ReactNode } from 'react'

type HelpTipProps = {
  definition: string
  label?: string
}

/** Inline “?” control with a one-sentence definition (also available as native title). */
export function HelpTip({ definition, label = 'What is this?' }: HelpTipProps) {
  const id = useId()
  const [open, setOpen] = useState(false)

  return (
    <span className="help-tip">
      <button
        type="button"
        className="help-tip-btn"
        aria-expanded={open}
        aria-controls={id}
        aria-label={label}
        title={definition}
        onClick={(e) => {
          e.preventDefault()
          e.stopPropagation()
          setOpen((v) => !v)
        }}
        onBlur={() => setOpen(false)}
      >
        ?
      </button>
      {open && (
        <span className="help-tip-popover" id={id} role="tooltip">
          {definition}
        </span>
      )}
    </span>
  )
}

type FieldLabelProps = {
  text: string
  definition: string
  children: ReactNode
}

/** Form field: plain-English label + help + control. */
export function FieldLabel({ text, definition, children }: FieldLabelProps) {
  return (
    <label>
      <span className="label-row">
        <span className="label-text">{text}</span>
        <HelpTip definition={definition} />
      </span>
      {children}
    </label>
  )
}

type HeadingWithHelpProps = {
  as?: 'h2' | 'h3' | 'span'
  text: string
  definition: string
  className?: string
}

export function HeadingWithHelp({
  as: Tag = 'h2',
  text,
  definition,
  className,
}: HeadingWithHelpProps) {
  return (
    <Tag className={className ? `heading-with-help ${className}` : 'heading-with-help'}>
      <span>{text}</span>
      <HelpTip definition={definition} />
    </Tag>
  )
}
