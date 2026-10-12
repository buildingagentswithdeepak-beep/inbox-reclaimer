import {Audio} from '@remotion/media';
import {Img, AbsoluteFill, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {colors, enter} from './continuation/Shared';

export const GmailCleanupEndCard = ({audio = true}: {audio?: boolean}) => {
  const t = useCurrentFrame() / useVideoConfig().fps;
  const logo = enter(t, 0, .55);
  const request = enter(t, .3, .95);
  const pills = enter(t, .8, 1.45);
  const footer = enter(t, 1.4, 2.2);

  return <AbsoluteFill className="film" style={{background: colors.background}}>
    <div style={{position: 'absolute', left: 80, right: 80, top: 43, display: 'flex', justifyContent: 'space-between', color: colors.muted, fontSize: 20, letterSpacing: 2}}>
      <span>GMAIL CLEANUP AGENT / CLOSING</span><span style={{color: colors.blue}}>12 / END CARD</span>
    </div>

    <div style={{position: 'absolute', left: 150, top: 196, width: 530, height: 530, borderRadius: 42, background: 'linear-gradient(180deg, #f6f6f2, #ebe9e0)', display: 'grid', placeItems: 'center', transform: `translateY(${34 * (1 - logo)}px) scale(${0.92 + .08 * logo})`, boxShadow: `0 30px 100px ${logo > 0 ? '#0005' : 'transparent'}`}}>
      <Img src={staticFile('building-agents-logo.png')} style={{width: 420, height: 280, objectFit: 'contain'}}/>
    </div>

    <div style={{position: 'absolute', left: 790, right: 140, top: 222, opacity: request, transform: `translateY(${26 * (1 - request)}px)`}}>
      <div className="display" style={{fontSize: 92, lineHeight: '96px', letterSpacing: -3.2}}>Subscribe for more builds.</div>
      <div className="display" style={{fontSize: 92, lineHeight: '96px', letterSpacing: -3.2, color: colors.amber, marginTop: 12}}>Like if this helped.</div>
      <div style={{marginTop: 30, fontSize: 31, lineHeight: '43px', color: colors.muted}}>Practical agent workflows. Real review boundaries. No hype.</div>
    </div>

    <div style={{position: 'absolute', left: 790, right: 220, top: 642, display: 'flex', gap: 24, opacity: pills, transform: `translateY(${18 * (1 - pills)}px)`}}>
      <div style={{height: 82, padding: '0 38px', borderRadius: 999, background: '#173253', border: `1px solid ${colors.blue}`, color: colors.text, fontSize: 31, fontWeight: 700, display: 'flex', alignItems: 'center'}}>Subscribe</div>
      <div style={{height: 82, padding: '0 38px', borderRadius: 999, background: '#2f2619', border: `1px solid ${colors.amber}`, color: colors.text, fontSize: 31, fontWeight: 700, display: 'flex', alignItems: 'center'}}>Like</div>
    </div>

    <div style={{position: 'absolute', left: 150, right: 150, bottom: 88, display: 'flex', justifyContent: 'space-between', alignItems: 'center', opacity: footer}}>
      <div style={{fontSize: 24, color: colors.muted}}>Building Agents</div>
      <div style={{fontSize: 20, letterSpacing: 2, color: colors.blue}}>5 SECOND END CARD</div>
    </div>
    {audio && <Audio src={staticFile('audio/endcard-short-mix.wav')} volume={1}/>}
  </AbsoluteFill>;
};
