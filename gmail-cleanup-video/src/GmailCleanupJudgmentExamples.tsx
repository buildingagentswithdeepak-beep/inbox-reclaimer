import {AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {AudioBed, colors, enter, FictionalInbox, IllustrativeDemoLabel, inboxLayout} from './continuation/Shared';

// Register at 1920 x 1080, 60 fps, 1800 frames. The final layout is a match-cut contract.
export const GmailCleanupJudgmentExamples = ({audio = true}: {audio?: boolean}) => {
  const t = useCurrentFrame() / useVideoConfig().fps;
  const beat = t < 4 ? 0 : t < 8 ? 1 : t < 14 ? 2 : 3;
  const beatStart = [0, 4, 8, 14][beat];
  const arrival = enter(t, beatStart, beatStart + .45);
  const judgment = enter(t, 8, 8.55) * (1 - enter(t, 13.5, 14));
  const previewArrival = enter(t, 17, 17.5);
  const comparison = t >= 25;
  const paired = t >= 27;
  const editorial = [
    {label: '01 / PROJECT UPDATE', title: 'An answer still matters.', body: 'The milestone review needs a reply. Keep the context for the follow-up.', note: 'Useful work is not clutter.'},
    {label: '02 / PURCHASE RECEIPT', title: 'Keep the reference.', body: 'A receipt may be quiet today and useful later. It stays in this example.', note: 'Low attention does not mean low value.'},
    {label: '03 / FAVOURITE NEWSLETTER', title: 'A pattern is not a verdict.', body: 'Field Notes is a newsletter. It is also something I genuinely enjoy reading.', note: 'My judgment: leave this newsletter alone.'},
    {label: 'YOUR CONTEXT / YOUR CHOICE', title: 'Keep what matters.', body: 'The newsletter returns to its normal style. No message moved. No selection was approved.', note: 'The application finds patterns, not personal value.'},
  ][beat];

  return <AbsoluteFill className="film" style={{background: 'radial-gradient(ellipse at 85% 70%, #1b3552, #0a1422 73%)'}}>
    <div style={{position: 'absolute', left: 80, right: 80, top: 43, display: 'flex', justifyContent: 'space-between', color: colors.muted, fontSize: 20, letterSpacing: 2}}>
      <span>GMAIL CLEANUP AGENT / THE EXAMPLE</span>
      <span style={{color: colors.blue}}>07 / HUMAN JUDGMENT</span>
    </div>
    <div className="display" style={{position: 'absolute', left: 80, top: 112, fontSize: 60}}>
      {comparison ? 'Preview comparison' : <>A candidate. <span style={{color: colors.amber}}>Not a verdict.</span></>}
    </div>
    <div style={{position: 'absolute', left: 83, top: 202, fontSize: 24, color: colors.muted}}>
      {comparison ? 'Two views of the same unchanged inbox. No cleanup has happened.' : 'A project update. A receipt. A favourite newsletter. Repeated store promotions.'}
    </div>

    <div style={{position: 'absolute', left: 80, top: 264, fontSize: 20, letterSpacing: 1.5, color: colors.blue}}>
      {comparison ? 'BEFORE' : 'FICTIONAL INBOX / ALL ROWS UNCHANGED'}
    </div>
    <div style={{position: 'absolute', left: 80, top: 300}}>
      <FictionalInbox judgment={judgment}/>
      {t < 8 && <div style={{position: 'absolute', left: 4, top: inboxLayout.rowsTop + beat * inboxLayout.rowHeight + 3, width: 832, height: 70, border: `2px solid ${colors.blue}`, borderRadius: 6, opacity: arrival, pointerEvents: 'none'}}/>}
      {t >= 17 && t < 25 && <div style={{position: 'absolute', left: 4, top: inboxLayout.rowsTop + 3 * inboxLayout.rowHeight + 3, width: 832, height: 3 * inboxLayout.rowHeight - 6, border: `2px solid ${colors.blue}`, borderRadius: 6, opacity: previewArrival, pointerEvents: 'none'}}/>}
    </div>

    {t < 17 && <div style={{position: 'absolute', left: 1000, top: 320, width: 840, opacity: arrival, transform: `translateY(${16 * (1 - arrival)}px)`}}>
      <div style={{fontSize: 20, letterSpacing: 2, color: beat === 2 ? colors.amber : colors.blue}}>{editorial.label}</div>
      <div className="display" style={{fontSize: 58, lineHeight: 1.16, letterSpacing: -2, marginTop: 29, maxWidth: 740}}>{editorial.title}</div>
      <div style={{fontSize: 30, lineHeight: 1.5, color: colors.muted, marginTop: 28, maxWidth: 730}}>{editorial.body}</div>
      <div style={{borderTop: `1px solid ${colors.border}`, paddingTop: 24, marginTop: 34, color: colors.amber, fontSize: 25, lineHeight: 1.5}}>{editorial.note}</div>
      <div style={{marginTop: 24, fontSize: 20, color: colors.muted}}>EDITORIAL EXAMPLE / NOT AN APPLICATION DECISION</div>
    </div>}

    {t >= 17 && t < 25 && <div style={{position: 'absolute', left: 1000, top: 264, width: 850, opacity: previewArrival}}>
      <div style={{fontSize: 20, letterSpacing: 1, color: colors.blue}}>RECORDED INTERFACE / SEPARATE REAL SENDER</div>
      <div style={{fontSize: 27, marginTop: 19}}>noreply@medium.com</div>
      <div style={{fontSize: 20, color: colors.muted, marginTop: 8}}>Recorded sender variable: $sender. Not the fictional store.</div>
      <Img src={staticFile('suggest-command.png')} style={{display: 'block', width: 850, height: 104.72, marginTop: 22, borderRadius: 6}}/>
      <div style={{fontSize: 20, color: colors.muted, marginTop: 14}}>Genuine command capture / held for readability</div>

      <div style={{borderTop: `1px solid ${colors.border}`, marginTop: 25, paddingTop: 23}}>
        <div style={{fontSize: 20, letterSpacing: 1, color: colors.amber}}>SYNTAX EXAMPLE / NOT EXECUTED</div>
        <div style={{fontFamily: 'Consolas, monospace', whiteSpace: 'pre', fontSize: 23, lineHeight: 1.55, color: '#d6e7ff', marginTop: 17}}>{'reclaim --workspace-scripts $helper `\n  sender-cleanup `\n  --sender offers@northstar.example `\n  --max-messages 20 --redact-subjects'}</div>
        <div style={{fontSize: 22, color: colors.amber, marginTop: 17}}>Preview only. No --execute. No approval.</div>
        <div style={{fontSize: 21, lineHeight: 1.5, color: colors.muted, marginTop: 12}}>One exact sender, separate from Field Notes.<br/>No fictional output or saved plan is being shown.</div>
      </div>
    </div>}

    {comparison && !paired && <div style={{position: 'absolute', left: 1000, top: 360, width: 800, opacity: enter(t, 25, 25.45)}}>
      <div style={{fontSize: 20, letterSpacing: 2, color: colors.blue}}>NEXT / MATCHED VIEWS</div>
      <div className="display" style={{fontSize: 58, lineHeight: 1.2, letterSpacing: -2, marginTop: 27}}>Same inbox.<br/>Still unchanged.</div>
      <div style={{fontSize: 27, lineHeight: 1.5, color: colors.muted, marginTop: 28}}>Freeze the example for comparison.<br/>A preview is not permission to act.</div>
    </div>}

    {paired && <>
      <div style={{position: 'absolute', left: 1000, top: 264, fontSize: 20, letterSpacing: 1.5, color: colors.blue}}>BEFORE / PREVIEW COMPARISON</div>
      <div style={{position: 'absolute', left: 1000, top: 300}}><FictionalInbox/></div>
      <div style={{position: 'absolute', left: 959, top: 300, width: 2, height: 590, background: colors.border}}/>
    </>}

    <div style={{position: 'absolute', left: 83, top: 917, fontSize: 23, color: colors.muted}}>
      {comparison ? 'Both panels are BEFORE. Retained rows stay in the same positions.' : t >= 17 ? 'Store promotions are a separate review question. Frequency alone is not a reason to delete.' : 'Keep for follow-up. Keep for reference. Keep because you value it.'}
    </div>
    <div style={{position: 'absolute', left: 80, right: 80, bottom: 38, display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
      <IllustrativeDemoLabel/>
      <span style={{fontSize: 20, color: colors.amber}}>NO CLEANUP APPROVED / NO MAIL CHANGED</span>
    </div>
    <AudioBed name="judgment" enabled={audio}/>
  </AbsoluteFill>;
};
