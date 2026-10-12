import type {CSSProperties} from 'react';
import {Audio} from '@remotion/media';
import {AbsoluteFill, Easing, Img, interpolate, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

const C = {navy: '#0a1422', blue: '#74adff', amber: '#ffcb77', paper: '#f5f4ee', ink: '#192839'};
const ease = Easing.bezier(0.22, 1, 0.36, 1);
const motion = (t: number, start: number, end: number, a = 0, b = 1) => interpolate(t, [start, end], [a, b], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
const linear = (t: number, start: number, end: number, a = 0, b = 1) => interpolate(t, [start, end], [a, b], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

const Icon = ({kind, size = 24, color = 'currentColor'}: {kind: string; size?: number; color?: string}) => {
  const paths: Record<string, React.ReactNode> = {
    menu: <path d="M4 6h16M4 12h16M4 18h16"/>,
    search: <><circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/></>,
    mail: <><rect x="3" y="5" width="18" height="14" rx="3"/><path d="m4 7 8 6 8-6"/></>,
    star: <path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1 6.2-5.5-2.9-5.5 2.9 1-6.2L3 9.6l6.2-.9Z"/>,
    arrow: <path d="M4 12h16m-6-6 6 6-6 6"/>,
    lock: <><rect x="5" y="10" width="14" height="11" rx="3"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/></>,
    warning: <><path d="m12 3 10 18H2Z"/><path d="M12 9v5m0 3v.1"/></>,
    check: <path d="m5 12 4 4L20 5"/>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/></>,
    down: <path d="m6 9 6 6 6-6"/>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{paths[kind] ?? paths.mail}</svg>;
};

const GmailMark = () => <svg width="51" height="39" viewBox="0 0 48 36" fill="none"><path d="M4 32V7l20 15L44 7v25" stroke="#4285f4" strokeWidth="7" strokeLinejoin="round"/><path d="M4 7 24 22 44 7" stroke="#ea4335" strokeWidth="7" strokeLinejoin="round"/><path d="M4 7v25" stroke="#34a853" strokeWidth="7"/><path d="M44 7v25" stroke="#fbbc04" strokeWidth="7"/></svg>;

const Cursor = ({x, y, opacity = 1}: {x: number; y: number; opacity?: number}) => <svg width="62" height="79" viewBox="0 0 40 52" style={{position: 'absolute', left: x, top: y, opacity, filter: 'drop-shadow(0 5px 5px #0005)', zIndex: 9}}><path d="M4 3v35l9-8 8 17 7-4-8-16 13-1Z" fill="#fff" stroke="#152033" strokeWidth="2.5" strokeLinejoin="round"/></svg>;

const emails = [
  ['Northstar Studio', 'Project update: ready for your review', 'The latest files are attached.', '9:42 AM', true],
  ['Field & Form', 'One more offer, just for you', 'Your weekly offers are here.', '9:39 AM', false],
  ['Field & Form', 'Last chance: your weekend edit', 'Take another look before Sunday.', '9:31 AM', false],
  ['The Weekly Dispatch', 'A little inspiration for your Friday', 'Five things worth reading.', '9:20 AM', true],
  ['Field & Form', 'Still thinking it over?', 'A reminder from your saved collection.', '9:12 AM', false],
  ['Atlas Supply', 'Your purchase receipt', 'Thanks for shopping with us.', '9:04 AM', true],
  ['Field & Form', 'New arrivals. Same great finds.', 'Discover the latest collection.', '8:51 AM', false],
  ['Field & Form', 'Your members-only update', 'A fresh offer in your inbox.', '8:37 AM', false],
  ['Cedar Events', 'This week in your community', 'Here is what is coming up.', '8:26 AM', false],
  ['Field & Form', 'The collection everyone is talking about', 'Get a first look.', '8:12 AM', false],
  ['Northstar Studio', 'Notes from our last meeting', 'A quick recap for the team.', 'Yesterday', true],
  ['Field & Form', 'A fresh offer for a fresh week', 'Something you might like.', 'Yesterday', false],
] as const;

const Inbox = ({time, frozen = false, highlighted = false}: {time: number; frozen?: boolean; highlighted?: boolean}) => {
  const scanTime = frozen ? 3.99 : Math.min(time, 3.99);
  const count = Math.floor(linear(scanTime, 0, 3.85, 12482, 12846)).toLocaleString('en-US');
  const scroll = time < 4 && !frozen ? linear(time, 1.3, 3.9, 0, 235) : 0;
  return <div className="ui" style={{width: 1640, height: 670, background: '#f7f9fc', borderRadius: 20, overflow: 'hidden', boxShadow: '0 30px 90px #0004'}}>
    <div style={{height: 39, background: '#e4e8ef', display: 'flex', alignItems: 'center', padding: '0 20px', gap: 8}}>
      {['#dd7773', '#e7bb66', '#83b899'].map(c => <span key={c} style={{width: 10, height: 10, borderRadius: 20, background: c}}/>)}
      <div style={{margin: '0 auto', fontSize: 15, color: '#657185'}}>Illustrative inbox / fictional messages</div>
    </div>
    <div style={{height: 92, display: 'flex', alignItems: 'center', gap: 27, padding: '0 28px'}}>
      <Icon kind="menu"/><GmailMark/><span style={{fontSize: 33, color: '#4a5565', marginLeft: -13}}>Gmail</span>
      <div style={{marginLeft: 54, height: 59, width: 900, borderRadius: 30, background: '#eaf0f8', display: 'flex', alignItems: 'center', padding: '0 24px', gap: 22, color: '#68788d', fontSize: 22}}><Icon kind="search"/>Search mail</div>
      <div style={{marginLeft: 'auto', height: 43, width: 43, borderRadius: 30, background: '#dfebfc', display: 'grid', placeItems: 'center', color: '#456999', fontSize: 20}}>D</div>
    </div>
    <div style={{display: 'flex', height: 539}}>
      <div style={{width: 259, flexShrink: 0, padding: '0 18px'}}>
        <div style={{width: 174, padding: '22px 24px', background: '#c3e6fd', borderRadius: 17, fontSize: 22, marginBottom: 27}}>+ Compose</div>
        {['Inbox', 'Starred', 'Snoozed', 'Sent', 'Drafts', 'More'].map((name, i) => <div key={name} style={{display: 'flex', alignItems: 'center', gap: 17, padding: '13px 15px', background: i === 0 ? '#d6e5fc' : 'transparent', borderRadius: 26, fontSize: 19, fontWeight: i === 0 ? 700 : 400}}><Icon kind={['mail', 'star', 'clock', 'arrow', 'mail', 'down'][i]} size={21}/>{name}{i === 0 && <span style={{marginLeft: 'auto', fontSize: 17}}>{count}</span>}</div>)}
      </div>
      <div style={{width: 1381, background: '#fff', borderTopLeftRadius: 18, overflow: 'hidden'}}>
        <div style={{height: 55, padding: '0 28px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: '#677487'}}><span style={{fontSize: 23}}>□ &nbsp; ↻ &nbsp; ⋮</span><span style={{fontSize: 17}}>1–50 of {count} &nbsp;&nbsp; ‹ &nbsp; ›</span></div>
        <div style={{display: 'flex', height: 61, borderBottom: '1px solid #d8dfeb'}}>{['Primary', 'Promotions', 'Social'].map((name, i) => <div key={name} style={{width: 320, display: 'flex', alignItems: 'center', gap: 16, paddingLeft: 30, borderBottom: i === 0 ? '4px solid #3879d4' : 'none', color: i === 0 ? '#2164bc' : '#657185', fontSize: 20}}><Icon kind="mail"/>{name}{i === 1 && <span style={{background: '#e3efe5', color: '#3d7051', padding: '4px 7px', borderRadius: 5, fontSize: 14}}>24 new</span>}</div>)}</div>
        <div style={{transform: `translateY(${-scroll}px)`}}>
          {[...emails, ...emails].map(([sender, subject, preview, stamp, keep], i) => <div key={i} style={{height: 65, display: 'flex', alignItems: 'center', gap: 19, padding: '0 25px', borderBottom: '1px solid #e3e8ef', background: highlighted && keep ? '#fff4dd' : i % 3 === 0 ? '#fff' : '#f0f4fa', boxShadow: highlighted && keep ? 'inset 4px 0 #d99d3c' : 'none', fontSize: 20, whiteSpace: 'nowrap'}}>
            <span style={{width: 17, height: 17, border: '1.5px solid #94a0b2', borderRadius: 2, flexShrink: 0}}/><Icon kind="star" size={19} color={keep ? '#d8a444' : '#92a0b1'}/>
            <span style={{width: 211, flexShrink: 0, fontWeight: 600}}>{sender}</span><span style={{fontWeight: 600}}>{subject}</span><span style={{color: '#8c97a6', overflow: 'hidden', textOverflow: 'ellipsis'}}>– {preview}</span><span style={{marginLeft: 'auto', fontSize: 16, paddingLeft: 18}}>{stamp}</span>
          </div>)}
        </div>
      </div>
    </div>
  </div>;
};

const TopBar = ({step, dark = true, label = 'ILLUSTRATIVE DEMO'}: {step: string; dark?: boolean; label?: string}) => <div style={{position: 'absolute', left: 86, right: 86, top: 48, display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: dark ? '#9cabbf' : '#647485'}}>
  <div className="eyebrow" style={{fontSize: 19}}>GMAIL CLEANUP AGENT <span style={{margin: '0 21px', opacity: .4}}>/</span> {step}</div>
  <div style={{fontSize: 18, letterSpacing: .2, border: `1px solid ${dark ? '#394658' : '#bac5cf'}`, padding: '10px 17px', borderRadius: 7}}>{label}</div>
</div>;

const Headline = ({children, t, start = 0, style = {}}: {children: React.ReactNode; t: number; start?: number; style?: CSSProperties}) => <div className="display" style={{fontSize: 83, lineHeight: 1.13, opacity: motion(t, start, start + .3), transform: `translateY(${motion(t, start, start + .55, 34, 0)}px)`, ...style}}>{children}</div>;

const StorageWarning = ({t}: {t: number}) => {
  const appear = motion(t, 4, 4.5);
  const fade = 1 - motion(t, 10.25, 10.75);
  return <div style={{position: 'absolute', left: 182, top: 410, width: 1556, opacity: appear * fade, transform: `translateY(${(1 - appear) * 50}px) scale(${.95 + .05 * appear})`, background: '#fcfcfa', color: C.ink, borderRadius: 26, padding: '28px 48px 27px', boxShadow: '0 34px 100px #0007'}}>
    <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 22, fontSize: 18, color: '#6b7685'}}><span style={{letterSpacing: 1.6}}>YOUR GMAIL SCREENSHOT</span><span>Cropped for privacy</span></div>
    <Img src={staticFile('storage-warning.png')} style={{display: 'block', width: 1460, height: 196, borderRadius: 22}}/>
    <div style={{display: 'flex', justifyContent: 'space-between', gap: 35, marginTop: 24, fontSize: 18, color: '#647387'}}><span>Google storage is shared across Gmail, Drive and Photos.</span><span>Price and date shown as captured; not a current offer.</span></div>
  </div>;
};

const Hook = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  // The first three shots cut into one consistent inbox, not three unrelated screens.
  const cut = t < 1.3 ? 0 : t < 2.6 ? 1 : t < 4 ? 2 : 3;
  const pullback = motion(t, 10.35, 11.35);
  const scale = cut === 0 ? motion(t, 0, 1.3, 1.02, 1.07) : cut === 1 ? 1.29 : cut === 2 ? 1.13 : 1 - .045 * pullback;
  const x = cut === 1 ? -225 : cut === 2 ? -70 : 0;
  const y = cut === 1 ? -65 : cut === 2 ? -15 : 0;
  const scrim = t >= 4 ? .63 * (1 - motion(t, 10.3, 11.1)) : 0;
  return <AbsoluteFill>
    <div style={{position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at 80% 85%, #1b334f 0%, #0a1422 67%)'}}/>
    <TopBar step={t < 4 ? 'THE BUILDUP' : t < 8 ? 'THE INTERRUPTION' : 'THE QUESTION'} label={t >= 4 && t < 10.75 ? 'SUPPLIED SCREENSHOT / ILLUSTRATIVE INBOX' : 'ILLUSTRATIVE DEMO'}/>
    <div style={{position: 'absolute', left: 91, top: 136, zIndex: 4}}>
      {t < 4 ? <Headline t={t} style={{fontSize: 80}}>An inbox that never<br/><span style={{color: C.blue}}>stops growing.</span></Headline> : t < 8 ? <Headline t={t} start={4}>Storage full.<br/><span style={{color: C.amber}}>Upgrade?</span></Headline> : <Headline t={t} start={8} style={{fontSize: 77}}>What&apos;s actually<br/><span style={{color: C.amber}}>worth keeping?</span></Headline>}
    </div>
    {t < 4 && <div style={{position: 'absolute', top: 167, right: 100, textAlign: 'right', opacity: motion(t, .25, .65)}}><div style={{fontSize: 78, fontWeight: 500, letterSpacing: -4, fontVariantNumeric: 'tabular-nums'}}>{Math.floor(linear(t, 0, 3.85, 12482, 12846)).toLocaleString('en-US')}</div><div style={{fontSize: 18, letterSpacing: 2, color: '#8ea4c2'}}>ILLUSTRATIVE INBOX COUNT</div></div>}
    <div style={{position: 'absolute', left: 0, right: 0, top: 350, bottom: 59, overflow: 'hidden'}}>
      <div style={{position: 'absolute', left: 140, top: 15, transform: `translate(${x}px, ${y}px) scale(${scale})`, transformOrigin: '50% 30%', filter: `blur(${scrim * 5}px)`}}><Inbox time={t} highlighted={t >= 10.8}/></div>
    </div>
    <div style={{position: 'absolute', inset: '343px 0 0', background: '#0a1422', opacity: scrim}}/>
    {t >= 4 && <StorageWarning t={t}/>}
    {t >= 8 && t < 10.8 && <Cursor x={interpolate(t, [8, 8.95, 9.55, 10.1], [1820, 1590, 1580, 1580], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease})} y={interpolate(t, [8, 8.95, 9.55], [860, 625, 620], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease})} opacity={1 - motion(t, 10.15, 10.5)}/>}
    {t >= 9.6 && t < 10.7 && <div className="pill" style={{position: 'absolute', right: 178, top: 284, color: C.amber, background: '#2c2a26', opacity: motion(t, 9.6, 9.8) * (1 - motion(t, 10.4, 10.7))}}>Pause. Not a purchase.</div>}
    <div style={{position: 'absolute', bottom: 19, left: 91, right: 91, display: 'flex', justifyContent: 'space-between', fontSize: 17, color: '#94a4b9'}}><span>Fictional emails. No account connected.</span><span>{t >= 4 ? 'Cleaning Gmail may help. It does not guarantee avoiding an upgrade.' : 'More messages. More decisions.'}</span></div>
  </AbsoluteFill>;
};

const Report = ({t}: {t: number}) => {
  const review = t >= 3.1;
  return <div className="ui" style={{background: '#ecf1f6', width: 985, height: 605, borderRadius: 18, overflow: 'hidden', boxShadow: '0 35px 90px #0005'}}>
    <div style={{height: 36, background: '#dce4ee', display: 'flex', alignItems: 'center', padding: '0 19px', gap: 7}}>{[0, 1, 2].map(i => <div key={i} style={{width: 8, height: 8, background: '#91a3b9', borderRadius: 10}}/>)}<span style={{marginLeft: 17, fontSize: 14, color: '#536980'}}>Local report recreation / synthetic data</span></div>
    <div style={{padding: '26px 31px', background: 'linear-gradient(110deg, #123147, #1b4562)', color: '#fff'}}>
      <div style={{letterSpacing: 1.8, fontSize: 13, color: '#a6c6de', marginBottom: 10}}>INBOX RECLAIMER / {review ? 'SENDER CLEANUP' : 'MAILBOX ANALYSIS'}</div>
      <div style={{fontSize: review ? 34 : 38, fontWeight: 650, letterSpacing: -1}}>{review ? 'Review before moving to Trash.' : 'Your mailbox, in perspective.'}</div>
      <div style={{display: 'flex', marginTop: 19, gap: 11}}><span className="pill" style={{background: review ? '#614c2b' : '#224f69', color: review ? '#ffdc9c' : '#c1e3ff', fontSize: 14}}>{review ? 'No approval · No mail changed' : 'ANALYSIS ONLY · NO MAIL CHANGED'}</span><span className="pill" style={{background: '#24495f', color: '#b6d3e6', fontSize: 14}}>SYNTHETIC DEMO</span></div>
    </div>
    {!review ? <div style={{padding: 24}}>
      <div style={{display: 'flex', gap: 12}}>{[['37', 'Messages inventoried'], ['28', 'Newsletter candidates'], ['0', 'Messages over 10 MB']].map(([value, label], i) => <div key={label} style={{flex: 1, background: '#fff', borderRadius: 11, padding: 19, borderTop: '3px solid #568cac', opacity: motion(t, .5 + i * .13, .9 + i * .13), transform: `translateY(${motion(t, .5 + i * .13, .9 + i * .13, 19, 0)}px)`}}><div style={{fontSize: 39, color: '#23496a', fontWeight: 600}}>{value}</div><div style={{fontSize: 16, color: '#698093', marginTop: 8}}>{label}</div></div>)}</div>
      <div style={{marginTop: 18, background: '#fff', borderRadius: 11, padding: '19px 22px'}}><div style={{display: 'flex', justifyContent: 'space-between', fontSize: 20, fontWeight: 600}}><span>Top senders by message count</span><span style={{fontSize: 14, color: '#7c8c9b'}}>SAMPLE REPORT</span></div>{[['Field & Form', '28', .84], ['The Weekly Dispatch', '6', .18], ['Northstar Studio', '3', .09]].map(([sender, count, width], i) => <div key={sender} style={{display: 'flex', alignItems: 'center', height: 49, fontSize: 17, gap: 20}}><span style={{width: 222}}>{sender}</span><div style={{flex: 1, height: 7, background: '#eff3f7', borderRadius: 4}}><div style={{width: `${Number(width) * motion(t, .95 + i * .15, 1.5 + i * .15) * 100}%`, height: '100%', background: '#6a9bd0', borderRadius: 4}}/></div><span style={{width: 29, textAlign: 'right', fontVariantNumeric: 'tabular-nums'}}>{count}</span></div>)}</div>
    </div> : <div style={{padding: 23}}>
      <div style={{background: '#fff', borderRadius: 11, padding: '18px 22px', boxShadow: 'inset 4px 0 #d4a34f'}}><div style={{fontSize: 23, fontWeight: 600}}>Bounded selection</div><div style={{fontSize: 17, marginTop: 10, color: '#687d90'}}>Exact sender: offers@example.test</div><div style={{fontSize: 17, marginTop: 7, color: '#687d90'}}>Account: creator@example.test &nbsp; / &nbsp; 28 eligible messages</div></div>
      <div style={{background: '#fff', borderRadius: 11, marginTop: 14, padding: '17px 22px'}}><div style={{fontSize: 20, fontWeight: 600}}>Exact eligible message list</div><div style={{display: 'flex', gap: 29, marginTop: 13, paddingBottom: 10, borderBottom: '1px solid #dce4ec', color: '#728497', fontSize: 15}}><span style={{width: 110}}>Message ID</span><span style={{width: 140}}>Date (UTC)</span><span style={{width: 150}}>Estimated bytes</span><span>Subject</span></div>{[1, 2].map(i => <div key={i} style={{display: 'flex', gap: 29, paddingTop: 13, fontSize: 15}}><span style={{width: 110}}>demo-{i.toString().padStart(3, '0')}</span><span style={{width: 140}}>2026-09-0{i}</span><span style={{width: 150}}>42,000</span><span>[redacted]</span></div>)}</div>
      <div style={{fontSize: 15, color: '#7b694f', marginTop: 15}}>This report cannot authorize execution.</div>
    </div>}
  </div>;
};

const Workflow = ({t}: {t: number}) => <div style={{position: 'absolute', left: 92, right: 92, top: 833, display: 'flex', gap: 0, alignItems: 'center', opacity: motion(t, .55, .95)}}>{['Analyze', 'Identify', 'Suggest', 'Review', 'Organize'].map((label, i) => {
  const active = t >= [.5, 1.15, 2, 3.1, 100][i];
  const color = i === 3 ? C.amber : i === 4 ? '#6b7889' : C.blue;
  return <div key={label} style={{display: 'flex', flex: i === 4 ? '0 0 260px' : 1, alignItems: 'center'}}><div style={{display: 'flex', alignItems: 'center', gap: 14, color: active ? color : '#637185'}}><span style={{display: 'grid', placeItems: 'center', width: 42, height: 42, fontSize: 16, border: `1px solid ${active ? color : '#35465b'}`, borderRadius: 30, background: active ? `${color}15` : 'transparent'}}>{i === 4 ? <Icon kind="lock" size={18}/> : `0${i + 1}`}</span><span style={{fontSize: 25, fontWeight: 500}}>{label}</span></div>{i !== 4 && <div style={{height: 1, background: active && i < 3 ? '#4a729f' : '#2b394c', flex: 1, margin: '0 25px'}}/>}</div>;
})}</div>;

const Reveal = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const exit = motion(t, 4.18, 4.55);
  const monitor = motion(t, 4.65, 5.55);
  return <AbsoluteFill>
    <div style={{position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at 85% 30%, #1b3653, #0a1422 66%)'}}/>
    <div style={{opacity: 1 - exit}}>
      <TopBar step="A BETTER STARTING POINT"/>
      <div style={{position: 'absolute', left: 92, top: 204, width: 690}}>
        <div className="eyebrow" style={{color: C.blue, fontSize: 19, opacity: motion(t, .05, .3)}}>INTRODUCING</div>
        <Headline t={t} start={.08} style={{fontSize: 82, marginTop: 22}}>Gmail<br/>Cleanup Agent<span style={{color: C.blue}}>.</span></Headline>
        <div style={{marginTop: 42, fontSize: 31, lineHeight: 1.8, letterSpacing: -.5}}>{['Find clutter.', 'Review first.', 'Stay in control.'].map((text, i) => <div key={text} style={{opacity: motion(t, [.6, 1.75, 2.9][i], [1, 2.15, 3.3][i]), transform: `translateX(${motion(t, [.6, 1.75, 2.9][i], [1, 2.15, 3.3][i], 25, 0)}px)`, color: i === 1 ? C.amber : '#d9e3ee'}}>{text}</div>)}</div>
      </div>
      <div style={{position: 'absolute', top: 187, left: 837, transform: `translateX(${motion(t, 0, .7, 280, 0)}px)`, opacity: motion(t, 0, .3)}}><Report t={t}/></div>
      <div style={{position: 'absolute', left: 854, top: 135, color: '#8ca4c0', fontSize: 16, letterSpacing: 1.1}}>SOURCE-BASED REPORT RECREATION · NOT A LIVE RUN</div>
      <Workflow t={t}/>
      <div style={{position: 'absolute', left: 92, right: 92, top: 930, paddingTop: 26, borderTop: '1px solid #2b394c', display: 'flex', justifyContent: 'space-between', alignItems: 'center', opacity: motion(t, 2.8, 3.2)}}><span style={{color: C.amber, fontSize: 24, display: 'flex', gap: 14, alignItems: 'center'}}><Icon kind="lock"/>Awaiting your review. Nothing moved.</span><span style={{color: '#92a4b9', fontSize: 20}}>A suggestion is not approval.</span></div>
    </div>
    {t >= 4.18 && <div style={{position: 'absolute', inset: 0, opacity: exit}}>
      <TopBar step="YOUR INBOX. YOUR DECISION."/>
      <div style={{position: 'absolute', top: 127, width: '100%', textAlign: 'center'}}><div className="display" style={{fontSize: 64, letterSpacing: -2}}>Find clutter. <span style={{color: C.amber}}>Review first.</span> Stay in control.</div><div style={{marginTop: 19, color: '#9badc4', fontSize: 23}}>Gmail Cleanup Agent</div></div>
      <div style={{position: 'absolute', left: 0, right: 0, top: 911, height: 170, background: 'linear-gradient(#283545,#142133)', borderTop: '2px solid #4b5868', opacity: monitor}}/>
      <div style={{position: 'absolute', left: 845, top: 825, width: 230, height: 118, background: 'linear-gradient(90deg,#1b2532,#566475,#253444)', clipPath: 'polygon(36% 0,64% 0,70% 79%,100% 94%,100% 100%,0 100%,0 94%,30% 79%)', opacity: monitor}}/>
      <div style={{position: 'absolute', left: 140, top: 336, transform: `translateY(${-monitor * 15}px) scale(${1 - monitor * .255})`, transformOrigin: '50% 0%'}}>
        <div style={{position: 'absolute', inset: -18, bottom: -50, borderRadius: 35, background: 'linear-gradient(120deg,#5c697a,#172231 40%,#3c4b60)', boxShadow: '0 35px 100px #0007', opacity: monitor}}/>
        <div style={{position: 'relative'}}><Inbox time={12} frozen highlighted/></div>
        <div style={{position: 'absolute', top: 683, width: '100%', display: 'flex', justifyContent: 'center', opacity: monitor}}><div style={{width: 8, height: 8, borderRadius: 8, background: '#b9c5d4'}}/></div>
      </div>
      <div style={{position: 'absolute', bottom: 30, left: 92, right: 92, display: 'flex', justifyContent: 'space-between', color: '#a6b6c9', fontSize: 18, opacity: monitor}}><span>Illustrative monitor handoff · fictional inbox</span><span>No approval. No mail changed.</span></div>
    </div>}
  </AbsoluteFill>;
};

export const GmailCleanupHook = ({audio = true}: {audio?: boolean}) => <AbsoluteFill className="film">
  <Sequence durationInFrames={720}><Hook/></Sequence>
  <Sequence from={720} durationInFrames={360}><Reveal/></Sequence>
  {audio && <><Audio src={staticFile('audio/music.wav')}/><Audio src={staticFile('audio/sfx.wav')}/></>}
</AbsoluteFill>;
