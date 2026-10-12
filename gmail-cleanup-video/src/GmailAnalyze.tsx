import {Audio, Video} from '@remotion/media';
import {AbsoluteFill, Easing, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

const blue = '#83b6ff';
const amber = '#ffd086';
const ease = (t: number, start: number, end: number) => interpolate(t, [start, end], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(.22, 1, .36, 1)});

export const GmailAnalyze = ({audio = true}: {audio?: boolean}) => {
  const t = useCurrentFrame() / useVideoConfig().fps;
  const opening = ease(t, 0, .65);
  const expand = ease(t, 3.35, 4);
  const handoff = ease(t, 10.5, 11.05);
  const scale = 1 - .31 * handoff;
  const x = 216 - 126 * handoff;
  const y = 348 - 108 * expand + 65 * handoff;
  const height = 218 + 520 * expand;
  const scan = interpolate(t, [.8, 10.5], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const across = ease(t, 10.9, 11.1);
  const markerX = (x - 22) * (1 - across) + 1190 * across;
  const scanY = y + 62 + scan * (height * scale - 170);
  const categoryY = interpolate(t, [11.3, 11.7, 12.1, 12.5], [313, 445, 577, 709], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  // Route above the shrinking capture, never across its recorded pixels.
  const rise = ease(t, 10.5, 10.9);
  const settle = ease(t, 11.1, 11.3);
  const markerY = (scanY * (1 - rise) + 260 * rise) * (1 - settle) + categoryY * settle;
  const markerHeight = 86 * (1 - rise) + 4 * rise + 68 * settle;
  return <AbsoluteFill className="film" style={{background: 'radial-gradient(ellipse at 80% 65%, #1b3552, #0a1422 73%)'}}>
    <div style={{position: 'absolute', left: 90, right: 90, top: 43, display: 'flex', justifyContent: 'space-between', fontSize: 17, color: '#9eb2cd', letterSpacing: 2}}><span>GMAIL CLEANUP AGENT / THE WORKFLOW</span><span style={{color: blue}}>01 / ANALYZE</span></div>
    <div className="display" style={{position: 'absolute', top: 111, left: 90, fontSize: 61, opacity: opening, transform: `translateY(${18 * (1 - opening)}px)`}}>1. ANALYZE <span style={{color: '#607b9d'}}>{'\u2014'}</span> <span style={{color: amber}}>No cleanup approved.</span></div>
    <div style={{position: 'absolute', top: 201, left: 93, color: '#a9bfd9', fontSize: 22}}>Read metadata. Understand the patterns. Leave mail unchanged.</div>

    <div style={{position: 'absolute', left: x, top: y, width: 1488, height, transform: `scale(${scale})`, transformOrigin: 'top left', border: '1px solid #52657f', borderRadius: 14, overflow: 'hidden', background: '#1a1a1a', boxShadow: '0 25px 80px #0005', opacity: opening}}>
      <div style={{height: 48, padding: '0 22px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#18283b', color: '#bacce1', fontSize: 16, letterSpacing: 1}}><span>{t < 4 ? 'RECORDED ANALYSIS COMMAND' : t < 10 ? 'READ-ONLY ANALYSIS OUTPUT' : 'CATEGORIES AND SUMMARY'}</span><span>IDENTIFIERS MASKED / NORMAL-SPEED EXCERPTS</span></div>
      <Video src={staticFile('analyze-15s.mp4')} muted style={{position: 'absolute', left: 0, top: 48, width: 1488, height: 684}}/>
    </div>

    <div style={{position: 'absolute', left: markerX, top: markerY, width: 4, height: markerHeight, borderRadius: 3, background: blue, boxShadow: '0 0 22px #65a7ff88', opacity: ease(t, .5, .8)}}/>
    <div style={{position: 'absolute', left: 216, top: 621, opacity: opening * (1 - expand), width: 1488, display: 'flex', gap: 24}}>
      {[['BOUNDED PREVIEW', '--max-messages 1000'], ['SUBJECTS REDACTED', '--redact-subjects'], ['REPORT OUTPUT', '--html $report']].map(([label, value]) => <div key={label} style={{flex: 1, padding: '27px 30px', borderTop: '1px solid #456283', background: '#122338'}}><div style={{fontSize: 16, color: '#8ca5c5', letterSpacing: 2, marginBottom: 16}}>{label}</div><div style={{fontFamily: 'monospace', fontSize: 25, color: blue}}>{value}</div></div>)}
    </div>

    <div style={{position: 'absolute', top: 262, left: 1220, fontSize: 17, color: '#a8c1df', letterSpacing: 2, opacity: handoff}}>REPORT CATEGORIES / EDITORIAL HIGHLIGHTS</div>
    {['Promotions', 'Social', 'Updates', 'Forums'].map((name, i) => {
      const highlight = ease(t, 11.3 + i * .4, 11.65 + i * .4);
      return <div key={name} style={{position: 'absolute', left: 1220 + 35 * (1 - handoff), top: 306 + i * 132, width: 610, height: 112, opacity: handoff, border: `1px solid ${highlight > 0 ? '#6695cc' : '#304b6b'}`, borderRadius: 12, padding: '24px 28px', background: `rgba(51, 101, 158, ${.09 + .2 * highlight})`, overflow: 'hidden'}}><div style={{position: 'absolute', left: 0, bottom: 0, height: 3, width: `${highlight * 100}%`, background: blue}}/><span style={{fontSize: 16, color: '#8aa7cd', marginRight: 25}}>0{i + 1}</span><span className="display" style={{fontSize: 35, letterSpacing: -1, color: highlight > 0 ? '#d4e6ff' : '#8da2be'}}>{name}</span></div>;
    })}
    <div style={{position: 'absolute', left: 92, top: 847, opacity: handoff}}><div className="display" style={{fontSize: 40, letterSpacing: -1.5}}>Patterns, <span style={{color: blue}}>not permission.</span></div><div style={{fontSize: 21, color: '#a9bfd9', marginTop: 15}}>Category labels can overlap. No deletion recommendation.</div></div>
    <div style={{position: 'absolute', left: 90, right: 90, bottom: 38, display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 18, color: '#93acca'}}><span>Limited preview: up to 1,000 messages in Gmail listing order; not the full mailbox.</span><span style={{color: amber}}>READ ONLY / NO MAIL CHANGED</span></div>
    {audio && <><Audio src={staticFile('audio/analyze-music.wav')}/><Audio src={staticFile('audio/analyze-sfx.wav')}/></>}
  </AbsoluteFill>;
};
