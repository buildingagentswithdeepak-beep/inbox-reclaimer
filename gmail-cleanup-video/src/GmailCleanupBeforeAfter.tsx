import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {AudioBed, colors, enter, FictionalInbox, IllustrativeDemoLabel, inboxLayout} from './continuation/Shared';

// Usercomp2: 1920 x 1080, 60 fps, 1020 frames (17 seconds).
export const GmailCleanupBeforeAfter = ({audio = true}: {audio?: boolean}) => {
  const t = useCurrentFrame() / useVideoConfig().fps;
  const reveal = interpolate(t, [2, 6], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const settle = enter(t, 12, 14);
  const benefits = enter(t, 12.5, 14);
  const showingAfter = t >= 2;

  return <AbsoluteFill className="film" style={{background: 'radial-gradient(ellipse at 85% 70%, #1b3552, #0a1422 73%)'}}>
    <div style={{position: 'absolute', left: 80, right: 80, top: 43, display: 'flex', justifyContent: 'space-between', color: colors.muted, fontSize: 20, letterSpacing: 2}}>
      <span>GMAIL CLEANUP AGENT / THE EXAMPLE</span>
      <span style={{color: colors.blue}}>08 / BEFORE &amp; AFTER</span>
    </div>
    <div className="display" style={{position: 'absolute', left: 80, top: 112, fontSize: 54}}>Preview comparison</div>
    <div style={{position: 'absolute', left: 83, right: 80, top: 202, fontSize: 25, lineHeight: 1.3, color: colors.muted}}>
      Illustrative outcome after separate user approval; not a recorded result.
    </div>

    {/* Match the preceding scene's inbox coordinates before the final group move. */}
    <div style={{position: 'absolute', left: 80, top: 264, width: 1760, height: 626, transformOrigin: 'center center', transform: `translateY(${-24 * settle}px) scale(${1 - .12 * settle})`}}>
      <div style={{position: 'absolute', left: 0, top: 0, width: inboxLayout.width, fontSize: 25, lineHeight: '30px', whiteSpace: 'nowrap'}}>
        <span style={{color: colors.blue, marginRight: 22}}>BEFORE</span>
        <span style={{color: colors.muted}}>More clutter. More manual searching.</span>
      </div>
      <div style={{position: 'absolute', left: 920, top: 0, width: inboxLayout.width, fontSize: 25, lineHeight: '30px', whiteSpace: 'nowrap'}}>
        <span style={{color: showingAfter ? colors.green : colors.blue, marginRight: 22}}>{showingAfter ? 'AFTER' : 'BEFORE'}</span>
        <span style={{color: showingAfter ? colors.green : colors.muted}}>{showingAfter ? 'User-reviewed cleanup. Clearer view.' : 'More clutter. More manual searching.'}</span>
      </div>
      <div style={{position: 'absolute', left: 0, top: 36}}><FictionalInbox/></div>
      <div style={{position: 'absolute', left: 879, top: 36, width: 2, height: inboxLayout.height, background: colors.border}}/>
      <div style={{position: 'absolute', left: 920, top: 36, width: inboxLayout.width, height: inboxLayout.height}}>
        <FictionalInbox/>
        {/* The opaque after inbox reveals left-to-right without reflowing retained rows. */}
        <div style={{position: 'absolute', inset: 0, clipPath: `inset(0 ${(1 - reveal) * 100}% 0 0)`}}>
          <FictionalInbox after/>
          <div style={{position: 'absolute', inset: 0, borderRadius: 12, border: `2px solid ${colors.green}`, background: 'rgba(155, 212, 180, .055)', pointerEvents: 'none'}}/>
        </div>
        {t >= 2 && t < 6 && <div style={{position: 'absolute', left: reveal * (inboxLayout.width - 3), top: 0, width: 3, height: inboxLayout.height, background: colors.green, boxShadow: '0 0 18px #9bd4b455', pointerEvents: 'none'}}/>}
      </div>
    </div>

    <div style={{position: 'absolute', left: 186, right: 186, top: 880, display: 'flex', justifyContent: 'space-between', fontSize: 29, lineHeight: '36px', color: colors.green, opacity: benefits, transform: `translateY(${10 * (1 - benefits)}px)`}}>
      <span>Less manual searching</span>
      <span>Clearer focus</span>
      <span>Your decisions</span>
    </div>
    <div style={{position: 'absolute', left: 80, right: 80, top: 940, fontSize: 25, lineHeight: '32px', color: colors.muted}}>
      Moving to Trash does not immediately free storage.
    </div>
    <div style={{position: 'absolute', left: 80, right: 80, bottom: 38, display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
      <IllustrativeDemoLabel/>
      <span style={{fontSize: 20, color: colors.amber}}>EDITORIAL ASSUMPTION / NOT A RECORDED RUN</span>
    </div>
    <AudioBed name="comparison" enabled={audio}/>
  </AbsoluteFill>;
};
