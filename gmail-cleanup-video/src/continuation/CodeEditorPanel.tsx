import source from '../data/continuation-code.json';
import {colors} from './Shared';

export type CodeWindow = {id: string; startLine?: number; endLine?: number; label?: string};

// Tokenize once, retaining every character, including original line terminators.
const pythonTokens = /("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\\r\n])*"|'(?:\\.|[^'\\\r\n])*')|(#[^\r\n]*)|\b(False|None|True|and|as|assert|async|await|break|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield)\b|\b(\d+(?:\.\d+)?)\b/g;
const excerpts = new Map(source.excerpts.map((excerpt) => {
  const lines = (excerpt.code.match(/[^\r\n]*(?:\r\n|\n|\r|$)/g) ?? []).filter((line) => line !== '');
  const highlighted = lines.map((text, index) => {
    const tokens: {text: string; color: string}[] = [];
    let cursor = 0;
    for (const match of text.matchAll(pythonTokens)) {
      const at = match.index;
      if (at > cursor) tokens.push({text: text.slice(cursor, at), color: colors.text});
      tokens.push({text: match[0], color: match[1] ? colors.green : match[2] ? '#a0b0c7' : match[3] ? '#c6afff' : colors.amber});
      cursor = at + match[0].length;
    }
    if (cursor < text.length) tokens.push({text: text.slice(cursor), color: colors.text});
    return {number: excerpt.startLine + index, tokens};
  });
  if (highlighted.flatMap((line) => line.tokens.map((token) => token.text)).join('') !== excerpt.code) {
    throw new Error(`Tokenization changed source: ${excerpt.id}`);
  }
  return [excerpt.id, {...excerpt, lines: highlighted}] as const;
}));

export const CodeEditorPanel = ({windows, tabs, accent}: {
  windows: readonly CodeWindow[];
  tabs: readonly string[];
  accent: string;
}) => {
  const blocks = windows.map((window) => {
    const excerpt = excerpts.get(window.id);
    if (!excerpt) throw new Error(`Unknown source excerpt: ${window.id}`);
    const first = window.startLine ?? excerpt.startLine;
    const last = window.endLine ?? excerpt.endLine;
    if (first < excerpt.startLine || last > excerpt.endLine || first > last) throw new Error(`Invalid source window: ${window.id}`);
    return {...excerpt, first, last, label: window.label ?? excerpt.symbol, lines: excerpt.lines.filter((line) => line.number >= first && line.number <= last)};
  });
  const active = blocks[0].file;
  const compact = blocks.length > 1;

  return <div data-code-editor style={{position: 'absolute', left: 80, top: 300, width: 1760, height: 570, boxSizing: 'border-box', border: `1px solid ${colors.border}`, borderRadius: 12, background: '#0d1b2b', boxShadow: '0 24px 60px #0004', color: colors.text}}>
    <div style={{height: 54, display: 'flex', alignItems: 'stretch', background: colors.panel, borderRadius: '12px 12px 0 0', borderBottom: `1px solid ${colors.border}`, paddingLeft: 14}}>
      {tabs.map((file) => <div key={file} style={{display: 'flex', alignItems: 'center', gap: 12, padding: '0 24px', fontSize: 22, borderTop: `3px solid ${file === active ? accent : 'transparent'}`, background: file === active ? '#0d1b2b' : 'transparent', color: file === active ? accent : colors.muted}}>
        <span style={{fontSize: 16, fontWeight: 700}}>PY</span>{file.replace('src/inbox_reclaimer/', '')}
      </div>)}
      <span style={{marginLeft: 'auto', alignSelf: 'center', paddingRight: 24, fontSize: 18, letterSpacing: 1.5, color: colors.muted}}>SOURCE / READ ONLY</span>
    </div>
    <div style={{height: 46, padding: '10px 26px', fontSize: 22, lineHeight: '26px', borderBottom: '1px solid #24384f', color: colors.muted}}>{active}</div>
    <div style={{height: 436, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: compact ? 4 : 0, padding: '4px 0'}}>
      {blocks.map((block) => <section key={`${block.id}-${block.first}`} data-excerpt={block.id} data-source-file={block.file} data-source-sha256={block.sourceSha256} data-excerpt-sha256={block.excerptSha256}>
        <div style={{height: compact ? 24 : 36, paddingLeft: 108, fontSize: compact ? 18 : 20, lineHeight: compact ? '24px' : '28px', color: accent}}>
          {block.label} <span style={{color: colors.muted}}> / L{block.first}-{block.last}</span>
        </div>
        {block.lines.map((line) => {
          const highlight = block.highlightRanges.some((range) => line.number >= range.startLine && line.number <= range.endLine);
          return <div key={line.number} data-source-line={line.number} data-highlighted={highlight} style={{display: 'flex', height: compact ? 31 : 39, lineHeight: `${compact ? 31 : 39}px`, borderLeft: `3px solid ${highlight ? accent : 'transparent'}`, background: highlight ? `${accent}10` : 'transparent', fontFamily: 'Consolas, "Courier New", monospace', fontSize: 24, fontVariantLigatures: 'none', letterSpacing: 0}}>
            <span aria-hidden style={{width: 83, flexShrink: 0, paddingRight: 20, textAlign: 'right', fontSize: 20, color: highlight ? accent : '#8094ae', borderRight: '1px solid #24384f', userSelect: 'none'}}>{line.number}</span>
            <code style={{display: 'block', paddingLeft: 22, paddingRight: 22, whiteSpace: 'pre', fontFamily: 'inherit', fontSize: 'inherit', lineHeight: 'inherit'}}>{line.tokens.map((token, index) => <span key={index} style={{color: token.color}}>{token.text}</span>)}</code>
          </div>;
        })}
      </section>)}
    </div>
    <div style={{height: 32, display: 'flex', justifyContent: 'space-between', padding: '4px 24px', borderTop: '1px solid #24384f', color: colors.muted, fontSize: 18, lineHeight: '23px'}}>
      <span>Python / UTF-8 / Original indentation</span><span>{compact ? 'Separate source ranges / intervening lines not shown' : 'Verbatim source excerpt / not execution output'}</span>
    </div>
  </div>;
};
