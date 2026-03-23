type HighlightedTextProps = {
  text: string;
  className?: string;
};

export function HighlightedText({ text, className }: HighlightedTextProps) {
  return <span className={className} dangerouslySetInnerHTML={{ __html: text }} />;
}
