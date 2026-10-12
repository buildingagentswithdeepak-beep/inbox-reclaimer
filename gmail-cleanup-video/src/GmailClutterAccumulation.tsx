import {Audio} from '@remotion/media';
import {AbsoluteFill, Easing, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

const blue = '#83b6ff';
const amber = '#ffd086';
const ease = Easing.bezier(.22, 1, .36, 1);
const progress = (time: number, start: number, end: number) => interpolate(time, [start, end], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
export const arrivalTimes = Array.from({length: 24}, (_, i) => 3 + 16.8 * (1 - .89 ** i) / (1 - .89 ** 23));

const senders = ['Field & Form', 'The Weekly Dispatch', 'Field & Form', 'Cedar Events', 'Field & Form', 'Atlas Supply'];
const subjects = ['Your weekly offers are here', 'A few ideas worth reading', 'A fresh look at the new collection', 'Your community events this week', 'One more offer, just for you', 'Your members-only update'];

const MailIcon = ({size = 24, color = 'currentColor'}: {size?: number; color?: string}) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.6"><rect x="3" y="5" width="18" height="14" rx="3"/><path d="m4 7 8 6 8-6"/></svg>;
const Message = ({important = false, sender, subject, index = 0, category = 'PROMOTIONAL'}: {important?: boolean; sender: string; subject: string; index?: number; category?: string}) => <div style={{height: 64, display: 'flex', alignItems: 'center', gap: 17, padding: '0 23px', background: important ? '#fff2d9' : index % 2 ? '#f1f5fa' : '#f8faff', borderBottom: '1px solid #dce4ee', color: '#263b54', boxShadow: important ? 'inset 5px 0 #cf9d45' : 'none', whiteSpace: 'nowrap'}}>
  <span style={{width: 16, height: 16, border: '1.5px solid #96a4b7', borderRadius: 3, flexShrink: 0}}/><span style={{fontSize: 24, color: important ? '#b67e24' : '#8d9db2'}}>{important ? '★' : '☆'}</span>
  <span style={{width: 199, flexShrink: 0, fontSize: 18, fontWeight: 600}}>{sender}</span><span style={{fontSize: 19, flex: 1, fontWeight: important ? 600 : 500}}>{subject}</span>
  <span style={{fontSize: 12, fontWeight: 600, color: important ? '#876021' : '#547197', background: important ? '#f3ddb5' : '#e3ebf7', padding: '6px 9px', borderRadius: 5}}>{important ? 'IMPORTANT' : category}</span>
</div>;

export const GmailClutterAccumulation = ({audio = true}: {audio?: boolean}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  // A clamped picture clock makes the last 3.5 seconds an actual freeze, not idle motion.
  const pictureTime = Math.min(t, 20.5);
  const arrived = arrivalTimes.filter(start => pictureTime >= start).length;
  const arrivals = arrivalTimes.map(start => progress(pictureTime, start, start + .34));
  const stack = arrivals.reduce((sum, value) => sum + value, 0);
  const lastArrival = arrived ? arrivalTimes[arrived - 1] : -10;
  const pulse = Math.sin(Math.PI * Math.min(1, Math.max(0, (pictureTime - lastArrival) / .35)));
  const crowded = pictureTime >= 19.8;
  const phase = pictureTime < 3 ? 'A little breathing room.' : pictureTime < 9 ? 'A newsletter. An offer.' : pictureTime < 15 ? 'The same senders. Again.' : crowded ? 'Pause. Look at what matters.' : 'More arrivals. More decisions.';
  const turn = progress(pictureTime, 10.5, 11.1);
  return <AbsoluteFill className="film" style={{background: 'radial-gradient(ellipse at 80% 75%,#1e3754,#0a1422 70%)'}}>
    <div style={{position: 'absolute', left: 86, right: 86, top: 48, display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}><span style={{fontSize: 18, letterSpacing: 2.3, color: '#9caec6', fontWeight: 600}}>GMAIL CLEANUP AGENT <span style={{margin: '0 20px', color: '#496381'}}>/</span> CLUTTER ARRIVES GRADUALLY</span><span style={{fontSize: 17, color: '#a6bdd8', padding: '11px 17px', border: '1px solid #3b4e65', borderRadius: 7}}>ILLUSTRATIVE DEMO · FICTIONAL EMAILS</span></div>

    <div style={{position: 'absolute', left: 88, top: 133, right: 88}}>
      {pictureTime < 10.5 ? <><div className="display" style={{fontSize: 75, lineHeight: 1.15, color: '#f6f4ee'}}>It starts with a few emails.</div><div style={{fontSize: 30, color: '#a4b9d1', marginTop: 17}}>{phase}</div></> : <div style={{opacity: turn, transform: `translateY(${18 * (1 - turn)}px)`}}><div className="display" style={{fontSize: 67, lineHeight: 1.16}}>Promotional <span style={{color: amber}}>≠ automatically unwanted.</span></div><div style={{fontSize: 28, color: '#a9bdd5', marginTop: 21}}>A category is a signal. Your context decides what stays.</div></div>}
    </div>

    <div style={{position: 'absolute', left: 88, top: 310, width: 1370, height: 658, borderRadius: 19, background: '#f2f6fc', boxShadow: '0 28px 80px #0005', overflow: 'hidden'}}>
      <div style={{height: 81, display: 'flex', alignItems: 'center', gap: 19, padding: '0 25px', color: '#576b85', borderBottom: '1px solid #d6e0ec'}}><MailIcon size={35} color="#507fbb"/><span style={{fontSize: 28, fontWeight: 600, color: '#2d4561'}}>Inbox</span><div style={{marginLeft: 25, padding: '13px 22px', width: 570, background: '#e5edf7', borderRadius: 28, fontSize: 17, color: '#8b9aaf'}}>Search fictional mail</div><span style={{marginLeft: 'auto', fontSize: 18, fontVariantNumeric: 'tabular-nums', color: '#647b97'}}>{3 + arrived} messages</span></div>
      <div style={{height: 42, padding: '12px 25px', background: '#e7edf5', color: '#6c8098', display: 'flex', justifyContent: 'space-between', fontSize: 13, letterSpacing: 1.2}}><span>IMPORTANT MESSAGE KEPT IN VIEW</span><span>EDITORIAL ANCHOR / NOT AN AUTOMATIC SORT</span></div>
      <Message important sender="Northstar Studio" subject="Project update: ready for your review"/>
      <div style={{position: 'relative', height: 471, overflow: 'hidden'}}>
        <div style={{position: 'absolute', width: '100%', top: stack * 64}}><Message sender="Atlas Supply" subject="Your purchase receipt" index={0} category="RECEIPT"/><Message sender="The Weekly Dispatch" subject="This week's ideas worth keeping" index={1} category="NEWSLETTER"/></div>
        {arrivalTimes.map((start, i) => {
          if (pictureTime < start) return null;
          const entry = arrivals[i];
          const newer = arrivals.slice(i + 1).reduce((sum, value) => sum + value, 0);
          return <div key={i} style={{position: 'absolute', width: '100%', top: newer * 64, transform: `translateX(${(1 - entry) * 185}px)`, opacity: entry}}><Message sender={senders[i % senders.length]} subject={subjects[i % subjects.length]} index={i}/></div>;
        })}
        {pictureTime < 3.5 && <div style={{position: 'absolute', top: 219, width: '100%', textAlign: 'center', color: '#9baabd', opacity: 1 - progress(pictureTime, 2.5, 3.4)}}><MailIcon size={49} color="#bdcadd"/><div style={{marginTop: 13, fontSize: 22}}>Room to focus.</div></div>}
      </div>
      <div style={{position: 'absolute', bottom: 0, right: 0, left: 0, height: 34, background: '#e8eff8', borderTop: '1px solid #d2dfef', color: '#6b7f98', fontSize: 14, padding: '9px 22px', display: 'flex', justifyContent: 'space-between'}}><span>{arrived > 4 ? 'More rows continue below the viewport. No messages removed.' : 'All messages remain in this illustrative inbox.'}</span><span>{crowded ? 'ARRIVALS PAUSED' : 'TIME PASSING · SIMULATED'}</span></div>
    </div>

    <div style={{position: 'absolute', left: 1500, right: 88, top: 326}}>
      <div style={{fontSize: 16, letterSpacing: 2, color: '#8ea5c2'}}>NEW ARRIVALS</div>
      <div style={{fontSize: 110, lineHeight: 1.1, marginTop: 18, fontWeight: 500, letterSpacing: -6, fontVariantNumeric: 'tabular-nums', color: '#f5f3eb', transform: `scale(${1 + pulse * .025})`, transformOrigin: 'left center'}}>{String(arrived).padStart(2, '0')}</div>
      <div style={{marginTop: 16, fontSize: 18, lineHeight: 1.5, color: '#8fa7c4'}}>Illustrative count.<br/>Not a storage measure.</div>
      <div style={{marginTop: 38, borderTop: '1px solid #3b506a', paddingTop: 24}}><div style={{fontSize: 22, lineHeight: 1.45, color: crowded ? amber : '#bed0e5'}}>{crowded ? 'Same inbox. More to consider.' : phase}</div></div>
      <div style={{marginTop: 39, padding: '21px 19px', border: '1px solid #775d36', borderRadius: 13, background: '#2e2c27'}}><div style={{fontSize: 14, letterSpacing: 1.3, color: amber}}>IMPORTANT MAIL</div><div style={{fontSize: 22, lineHeight: 1.4, color: '#f3dfbd', marginTop: 13}}>Still here.<br/>Still yours to decide.</div></div>
      <div style={{fontSize: 16, color: '#819ab9', lineHeight: 1.55, marginTop: 22}}>Promotional does not mean disposable.</div>
    </div>

    <div style={{position: 'absolute', left: 90, right: 90, bottom: 48, display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 20}}><span style={{color: '#9fb4cf'}}>More mail is not the same as more unwanted mail.</span><span style={{color: amber}}>No automatic deletion. No messages removed.</span></div>
    {audio && <><Audio src={staticFile('audio/clutter-music.wav')}/><Audio src={staticFile('audio/clutter-sfx.wav')}/></>}
  </AbsoluteFill>;
};
