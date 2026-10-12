import {Composition} from 'remotion';
import {GmailCleanupHook} from './GmailCleanupHook';
import {GmailIntroduction} from './GmailIntroduction';
import {GmailClutterAccumulation} from './GmailClutterAccumulation';
import {GmailReportReveal} from './GmailReportReveal';
import {GmailTechnicalStack} from './GmailTechnicalStack';
import {GmailAnalyze} from './GmailAnalyze';
import {GmailIdentify} from './GmailIdentify';
import {GmailSuggest} from './GmailSuggest';
import {GmailReviewOrganize} from './GmailReviewOrganize';
import {GmailCleanupJudgmentExamples} from './GmailCleanupJudgmentExamples';
import {GmailCleanupBeforeAfter} from './GmailCleanupBeforeAfter';
import {GmailCleanupArchitecture} from './GmailCleanupArchitecture';
import {GmailCleanupCodeTour} from './GmailCleanupCodeTour';
import {GmailCleanupEndCard} from './GmailCleanupEndCard';
import {GmailCleanupThumbnail} from './GmailCleanupThumbnail';

export const RemotionRoot = () => (
  <>
  <Composition id="GmailCleanupThumbnail" component={GmailCleanupThumbnail} width={1280} height={720} fps={30} durationInFrames={1} defaultProps={{}} />
  <Composition id="GmailCleanupEndCard" component={GmailCleanupEndCard} width={1920} height={1080} fps={60} durationInFrames={300} defaultProps={{audio: true}} />
  <Composition id="GmailCleanupCodeTour" component={GmailCleanupCodeTour} width={1920} height={1080} fps={60} durationInFrames={2640} defaultProps={{audio: true}} />
  <Composition id="GmailCleanupArchitecture" component={GmailCleanupArchitecture} width={1920} height={1080} fps={60} durationInFrames={1680} defaultProps={{audio: true}} />
  <Composition id="GmailCleanupBeforeAfter" component={GmailCleanupBeforeAfter} width={1920} height={1080} fps={60} durationInFrames={1020} defaultProps={{audio: true}} />
  <Composition id="GmailCleanupJudgmentExamples" component={GmailCleanupJudgmentExamples} width={1920} height={1080} fps={60} durationInFrames={1800} defaultProps={{audio: true}} />
  <Composition
    id="GmailReviewOrganize"
    component={GmailReviewOrganize}
    width={1920}
    height={1080}
    fps={60}
    durationInFrames={1800}
    defaultProps={{audio: true}}
  />
  <Composition
    id="GmailCleanupHook"
    component={GmailCleanupHook}
    width={1920}
    height={1080}
    fps={60}
    durationInFrames={1080}
    defaultProps={{audio: true}}
  />
  <Composition
    id="GmailIntroduction"
    component={GmailIntroduction}
    width={1920}
    height={1080}
    fps={60}
    durationInFrames={1080}
    defaultProps={{audio: true}}
  />
  <Composition
    id="GmailClutterAccumulation"
    component={GmailClutterAccumulation}
    width={1920}
    height={1080}
    fps={60}
    durationInFrames={1440}
    defaultProps={{audio: true}}
  />
  <Composition
    id="GmailReportReveal"
    component={GmailReportReveal}
    width={1920}
    height={1080}
    fps={60}
    durationInFrames={1140}
    defaultProps={{audio: true}}
  />
  <Composition
    id="GmailSuggest"
    component={GmailSuggest}
    width={1920}
    height={1080}
    fps={60}
    durationInFrames={480}
    defaultProps={{audio: true}}
  />
  <Composition
    id="GmailIdentify"
    component={GmailIdentify}
    width={1920}
    height={1080}
    fps={60}
    durationInFrames={600}
    defaultProps={{audio: true}}
  />
  <Composition
    id="GmailAnalyze"
    component={GmailAnalyze}
    width={1920}
    height={1080}
    fps={60}
    durationInFrames={900}
    defaultProps={{audio: true}}
  />
  <Composition
    id="GmailTechnicalStack"
    component={GmailTechnicalStack}
    width={1920}
    height={1080}
    fps={60}
    durationInFrames={600}
    defaultProps={{audio: true}}
  />
  </>
);
