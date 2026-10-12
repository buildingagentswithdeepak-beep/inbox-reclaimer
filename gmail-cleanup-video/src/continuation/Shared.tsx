import {Audio} from '@remotion/media';
import {Easing, interpolate, staticFile} from 'remotion';

export const colors = {
  background: '#0a1422',
  panel: '#132337',
  border: '#3b526e',
  text: '#f6f4ec',
  muted: '#adc2dc',
  blue: '#83b6ff',
  amber: '#ffd086',
  green: '#9bd4b4',
  review: '#392e20',
} as const;

export const enter = (t: number, a: number, b: number) => interpolate(t, [a, b], [0, 1], {
  extrapolateLeft: 'clamp',
  extrapolateRight: 'clamp',
  easing: Easing.bezier(.22, 1, .36, 1),
});

export const AudioBed = ({name, enabled = true}: {name: string; enabled?: boolean}) => enabled
  ? <Audio src={staticFile(`audio/continuation-${name}-mix.wav`)} volume={1}/>
  : null;

export const IllustrativeDemoLabel = () => <span style={{fontSize: 20, color: colors.muted}}>
  {'Illustrative demo \u00b7 fictional emails.'}
</span>;

export const inboxRows = [
  {id: 'project', sender: 'Project team', address: 'team@project.example', subject: 'Milestone review', context: 'Project update / follow-up', promotion: false},
  {id: 'receipt', sender: 'Travel desk', address: 'receipts@travel.example', subject: 'Your purchase receipt', context: 'Receipt / reference', promotion: false},
  {id: 'newsletter', sender: 'Field Notes', address: 'hello@fieldnotes.example', subject: 'A newsletter worth keeping', context: 'Favourite newsletter', promotion: false},
  {id: 'offer-weekend', sender: 'Northstar Store', address: 'offers@northstar.example', subject: 'Weekend offers', context: 'Store promotion', promotion: true},
  {id: 'offer-collection', sender: 'Northstar Store', address: 'offers@northstar.example', subject: 'The new collection', context: 'Store promotion', promotion: true},
  {id: 'offer-season', sender: 'Northstar Store', address: 'offers@northstar.example', subject: 'End-of-season offers', context: 'Store promotion', promotion: true},
] as const;

export const inboxLayout = {width: 840, height: 590, rowsTop: 88, rowHeight: 76} as const;

export const FictionalInbox = ({after = false, judgment = false, compact = false}: {
  after?: boolean;
  judgment?: boolean | number;
  compact?: boolean;
}) => {
  const emphasis = typeof judgment === 'boolean' ? Number(judgment) : Math.max(0, Math.min(1, judgment));
  return <div style={{position: 'relative', width: inboxLayout.width, height: inboxLayout.height, boxSizing: 'border-box', overflow: 'hidden', border: `1px solid ${colors.border}`, borderRadius: 12, background: colors.panel, color: colors.text, fontFamily: 'Inter, sans-serif', boxShadow: '0 24px 65px #0003'}}>
    <div style={{position: 'absolute', top: 0, left: 0, right: 0, height: inboxLayout.rowsTop, padding: '17px 24px', borderBottom: `1px solid ${colors.border}`}}>
      <div style={{fontSize: 25, fontWeight: 600, lineHeight: '30px'}}>Inbox</div>
      <div style={{marginTop: 3, lineHeight: '24px'}}><IllustrativeDemoLabel/></div>
    </div>
    {inboxRows.map((row, index) => {
      // Omit promotions without collapsing their slots or moving retained mail.
      if (after && row.promotion) return null;
      return <div key={row.id} style={{position: 'absolute', top: inboxLayout.rowsTop + index * inboxLayout.rowHeight, left: 0, right: 0, height: inboxLayout.rowHeight, borderBottom: '1px solid #2c415b', padding: '12px 24px', display: 'flex', gap: 24, alignItems: 'center'}}>
        {row.id === 'newsletter' && <div style={{position: 'absolute', inset: 3, borderRadius: 6, background: colors.review, border: `2px solid ${colors.amber}`, opacity: emphasis}}/>}
        <div style={{position: 'relative', width: 307, flexShrink: 0}}>
          <div style={{fontSize: 22, lineHeight: '27px', fontWeight: 600}}>{row.sender}</div>
          <div style={{fontSize: 20, lineHeight: '24px', color: colors.muted}}>{row.address}</div>
        </div>
        <div style={{position: 'relative', flex: 1, minWidth: 0}}>
          <div style={{fontSize: 22, lineHeight: '27px'}}>{row.subject}</div>
           <div style={{fontSize: 20, lineHeight: '24px', color: colors.muted}}>{row.context} / Oct {8 - index}</div>
        </div>
      </div>;
    })}
    {!compact && <div style={{position: 'absolute', left: 24, bottom: 12, fontSize: 20, lineHeight: '24px', color: colors.muted}}>Fictional example / not a live mailbox</div>}
  </div>;
};
