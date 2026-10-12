import {AbsoluteFill, Img, staticFile} from 'remotion';
import {colors} from './continuation/Shared';

export const GmailCleanupThumbnail = () => {
  return <AbsoluteFill style={{background: 'radial-gradient(ellipse at 82% 22%, #1a3551, #091320 70%)', fontFamily: 'Inter, sans-serif', color: colors.text}}>
    <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(90deg, rgba(9,19,32,.98) 0%, rgba(9,19,32,.95) 44%, rgba(9,19,32,.68) 66%, rgba(9,19,32,.2) 100%)'}}/>

    <div style={{position: 'absolute', left: 76, top: 58, fontSize: 20, letterSpacing: 3, color: colors.blue}}>GMAIL CLEANUP AGENT</div>

    <div className="display" style={{position: 'absolute', left: 72, top: 126, width: 650, fontSize: 88, lineHeight: '86px', letterSpacing: -4.5}}>
      Clean Gmail.<br/>
      <span style={{color: colors.amber}}>Keep control.</span>
    </div>

    <div style={{position: 'absolute', left: 78, top: 343, width: 520, fontSize: 33, lineHeight: '42px', color: '#c4d3e5'}}>
      Find clutter.<br/>Review first.<br/>You decide what stays.
    </div>

    <div style={{position: 'absolute', left: 78, top: 525, display: 'flex', alignItems: 'center', gap: 16}}>
      <div style={{padding: '12px 20px', borderRadius: 999, border: `1px solid ${colors.blue}`, background: '#143251', color: colors.blue, fontSize: 22, fontWeight: 700}}>REVIEW FIRST</div>
      <div style={{padding: '12px 20px', borderRadius: 999, border: `1px solid ${colors.amber}`, background: '#352a1b', color: colors.amber, fontSize: 22, fontWeight: 700}}>NO AUTO DELETE</div>
    </div>

    <div style={{position: 'absolute', right: 58, top: 44, width: 470, height: 612, overflow: 'hidden'}}>
      <div style={{position: 'absolute', inset: '16px 10px 0 40px', borderRadius: 34, background: 'linear-gradient(180deg, #25384f, #101d2c)', boxShadow: '0 24px 80px #0008'}}/>
      <Img src={staticFile('thumbnail-portrait.jpg')} style={{position: 'absolute', right: -24, top: 6, width: 458, height: 660, objectFit: 'cover', objectPosition: 'center 15%', filter: 'contrast(1.04) saturate(.96)'}}/>
      <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(180deg, rgba(9,19,32,0) 0%, rgba(9,19,32,.08) 58%, rgba(9,19,32,.4) 100%)'}}/>
    </div>

    <div style={{position: 'absolute', right: 82, top: 68, fontSize: 20, letterSpacing: 2, color: '#d6e4f7'}}>PYTHON • LANGGRAPH • GMAIL</div>
  </AbsoluteFill>;
};
