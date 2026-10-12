import {Audio, Video} from '@remotion/media';
import {AbsoluteFill, Easing, Img, interpolate, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

const amber = '#ffd086';
const blue = '#83b6ff';
const reveal = (t: number, start: number, end: number) => interpolate(t, [start, end], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(.22, 1, .36, 1)});

export const GmailReviewOrganize = ({audio = true}: {audio?: boolean}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  // Wait for full native-window dismissal, not just button focus, before changing status.
  const confirmed = frame >= 13 * fps;
  const organize = frame >= 14 * fps;
  const result = t >= 15 && t < 24;
  const gmail = t >= 24;
  const accent = confirmed ? blue : amber;
  const titleEntry = reveal(t, organize ? 14 : 0, organize ? 14.45 : .45);
  const evidenceEntry = reveal(t, gmail ? 24 : 15, gmail ? 24.45 : 15.45);

  return <AbsoluteFill className="film" style={{background: 'radial-gradient(ellipse at 85% 70%, #1b3552, #0a1422 73%)'}}>
    <div style={{position: 'absolute', top: 39, left: 70, right: 70, display: 'flex', justifyContent: 'space-between', fontSize: 17, letterSpacing: 2, color: '#9eb2cd'}}><span>GMAIL CLEANUP AGENT / THE WORKFLOW</span><span style={{color: accent}}>{organize ? '05 / ORGANIZE' : '04 / REVIEW'}</span></div>
    <div className="display" style={{position: 'absolute', top: 96, left: 70, fontSize: organize ? 53 : 62, opacity: titleEntry, transform: `translateY(${14 * (1 - titleEntry)}px)`}}>
      {organize ? '5. ORGANIZE' : '4. REVIEW'} <span style={{color: '#607b9d'}}>{'\u2014'}</span> <span style={{color: accent}}>{organize ? 'Approved action \u2192 Check results.' : 'You decide what stays.'}</span>
    </div>

    <Sequence durationInFrames={14 * fps}>
      <div style={{position: 'absolute', top: 201, left: 70, width: 1420, display: 'flex', justifyContent: 'space-between', color: '#aec4dd', fontSize: 15, letterSpacing: .8}}><span>RECORDED NATIVE CONFIRMATION / CONTINUOUS AT 1x</span><span>INTERNAL IDENTIFIERS MASKED</span></div>
      <div style={{position: 'absolute', top: 236, left: 70, width: 1420, height: 745.5, overflow: 'hidden', borderRadius: 8, boxShadow: `0 0 0 2px ${accent}, 0 24px 80px #0004`}}>
        <Video src={staticFile('review-organize-approval.mp4')} muted playbackRate={1} style={{width: 1420, height: 745.5}}/>
      </div>
      <div style={{position: 'absolute', left: 1540, top: 242, width: 310}}>
        <div style={{fontSize: 13, letterSpacing: 2, color: '#a9bad0'}}>EDITORIAL STATUS</div>
        <div style={{marginTop: 16, padding: '20px 17px', border: `1px solid ${accent}`, borderRadius: 9, color: accent, background: confirmed ? '#192e48' : '#392e20', fontSize: 26, lineHeight: 1.3, fontWeight: 600}}>{confirmed ? 'Confirmation recorded' : 'Awaiting your decision'}</div>
        <div style={{marginTop: 35, fontSize: 17, color: '#9eb2cd', letterSpacing: 1}}>REVIEW THE EXACT PLAN</div>
        <div style={{marginTop: 22, fontSize: 24, color: blue}}>noreply@medium.com</div>
        <div style={{marginTop: 24, display: 'flex', alignItems: 'baseline', gap: 15}}><span className="display" style={{fontSize: 82, color: amber}}>20</span><span style={{fontSize: 21, color: '#bbcce0'}}>selected</span></div>
        <div style={{fontSize: 28, marginTop: 10}}>Action: Trash</div>
        <div style={{fontSize: 21, marginTop: 21, lineHeight: 1.55, color: '#afc3dc'}}>Not immediate<br/>permanent deletion.</div>
        <div style={{marginTop: 34, borderTop: '1px solid #43566f', paddingTop: 24, fontSize: 22, lineHeight: 1.6, color: '#d0dcec'}}>Check the account.<br/>Review the selection.<br/>Cancel if unsure.</div>
        <div style={{marginTop: 26, fontSize: 18, lineHeight: 1.5, color: amber}}>No automatic approval.<br/>No recreated click.</div>
      </div>
    </Sequence>

    <Sequence from={14 * fps} durationInFrames={fps}>
      <div style={{position: 'absolute', left: 95, right: 95, top: 360, borderTop: `2px solid ${blue}`, paddingTop: 58}}><div style={{fontSize: 19, letterSpacing: 3, color: '#a9bed9'}}>SOURCE RECORDING / TIME JUMP</div><div className="display" style={{fontSize: 86, marginTop: 23}}>Later: run result</div><div style={{fontSize: 28, color: '#afc3dc', marginTop: 28}}>Confirmation first. Then inspect what the run reported.</div></div>
    </Sequence>

    {result && <>
      <div style={{position: 'absolute', top: 233, left: 90, right: 90, display: 'flex', justifyContent: 'space-between', fontSize: 17, letterSpacing: 1, color: '#a9bed9'}}><span>LATER: RECORDED RUN RESULT</span><span>HELD FOR READABILITY / INTERNAL IDENTIFIERS MASKED</span></div>
      <div style={{position: 'absolute', left: 90, top: 294, width: 1240, height: 556.74, borderRadius: 10, overflow: 'hidden', border: '1px solid #4a627f', background: '#181818', transform: `translateY(${16 * (1 - evidenceEntry)}px)`}}>
        <Img src={staticFile('review-organize-result.png')} style={{width: 1240, height: 556.74}}/>
        <svg width="1240" height="557" style={{position: 'absolute', inset: 0}}><rect x="61" y="321" width="300" height="133" rx="7" stroke={blue} strokeWidth="2" fill="none" pathLength="1" strokeDasharray="1" strokeDashoffset={1 - reveal(t, 15.65, 16.25)}/></svg>
      </div>
      <div style={{position: 'absolute', left: 1410, top: 296, width: 420}}>
        <div style={{fontSize: 16, letterSpacing: 2, color: '#a9bed9'}}>REPORTED COUNTS</div>
        <div style={{display: 'flex', alignItems: 'baseline', gap: 20, marginTop: 15}}><span className="display" style={{fontSize: 130, color: blue}}>20</span><span style={{fontSize: 28}}>confirmed</span></div>
        <div style={{display: 'flex', gap: 52, marginTop: 18}}>{['unknown', 'skipped'].map(label => <div key={label}><div className="display" style={{fontSize: 57}}>0</div><div style={{fontSize: 21, color: '#afc3dc'}}>{label}</div></div>)}</div>
        <div style={{marginTop: 35, paddingTop: 26, borderTop: '1px solid #42566e', fontSize: 23, lineHeight: 1.65, color: '#c3d1e3'}}>These are the run&apos;s results.<br/><span style={{color: amber}}>Not a new observation<br/>of the mailbox.</span></div>
      </div>
      <div style={{position: 'absolute', left: 94, top: 902, color: '#aec4dd', fontSize: 26}}>Same saved plan. Check confirmed, unknown, and skipped counts.</div>
    </>}

    {gmail && <>
      <div style={{position: 'absolute', top: 218, left: 90, right: 90, display: 'flex', justifyContent: 'space-between', color: '#a9bed9', fontSize: 17, letterSpacing: 1}}><span>LATER: GMAIL TRASH / RECORDED VISUAL CHECK</span><span>{t < 28 ? '1x PLAYBACK' : 'FINAL FRAME HELD'}</span></div>
      <div style={{position: 'absolute', left: 90, top: 268, width: 1260, height: 677.55, borderRadius: 10, overflow: 'hidden', background: '#f6f8fc', border: '1px solid #4a627f'}}>
        <Sequence from={24 * fps} durationInFrames={4 * fps}><Video src={staticFile('review-organize-gmail.mp4')} muted playbackRate={1} style={{width: 1260, height: 677.55}}/></Sequence>
        <Sequence from={28 * fps} durationInFrames={2 * fps}><Img src={staticFile('review-organize-gmail-hold.png')} style={{width: 1260, height: 677.55}}/></Sequence>
      </div>
      <div style={{position: 'absolute', left: 1420, top: 293, width: 410, opacity: evidenceEntry, transform: `translateY(${16 * (1 - evidenceEntry)}px)`}}>
        <div style={{fontSize: 16, color: blue, letterSpacing: 2}}>CHECK THE MAILBOX VIEW</div>
        <div className="display" style={{fontSize: 54, marginTop: 24, lineHeight: 1.18}}>Medium rows.<br/>In Gmail Trash.</div>
        <div style={{fontSize: 25, lineHeight: 1.6, marginTop: 32, color: '#bfd0e5'}}>A later visual check,<br/>separate from the<br/>local run output.</div>
        <div style={{borderTop: '1px solid #42566e', marginTop: 38, paddingTop: 29, fontSize: 23, lineHeight: 1.6, color: amber}}>Visible rows do not<br/>independently verify<br/>all 20 message IDs.</div>
        <div style={{fontSize: 21, marginTop: 31, color: '#afc3dc'}}>No invented folders or labels.</div>
      </div>
    </>}

    <div style={{position: 'absolute', left: 70, right: 70, bottom: 30, display: 'flex', justifyContent: 'space-between', fontSize: 18, color: '#9eb2cd'}}><span>{organize ? 'Trash is not immediate permanent deletion.' : 'Email addresses and subjects are visible. Native controls are preserved.'}</span><span style={{color: accent}}>{!confirmed ? 'AMBER BOUNDARY / HUMAN DECISION' : !organize ? 'RECORDED CONFIRMATION / RESULT NOT YET SHOWN' : 'ACTUAL FOOTAGE / EDITORIAL ANNOTATIONS'}</span></div>
    {audio && <><Audio src={staticFile('audio/review-organize-music.wav')}/><Audio src={staticFile('audio/review-organize-sfx.wav')}/></>}
  </AbsoluteFill>;
};
