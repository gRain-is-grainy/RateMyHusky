import {
  AbsoluteFill,
  Audio,
  Easing,
  Freeze,
  interpolate,
  Sequence,
  staticFile,
  useVideoConfig,
} from 'remotion';
import { TransitionSeries, linearTiming } from '@remotion/transitions';
import { fade } from '@remotion/transitions/fade';
import manifest from './manifest.json';
import { DARK, MUSIC } from './branding';
import { AskScene } from './scenes/AskScene';
import { Caption } from './components/Caption';
import { FootageScene } from './scenes/FootageScene';
import { IntroCard } from './scenes/IntroCard';
import { OutroCard } from './scenes/OutroCard';
import { driftFade } from './transitions/driftFade';
import { whipPan } from './transitions/whipPan';
import { zoomThrough } from './transitions/zoomThrough';
import { FPS, SCENES, TOTAL_FRAMES, TRANSITIONS } from './timing';

type SceneName = keyof typeof manifest.scenes;

// Speed up a clip so its full length fits the scene slot (capped at 2x;
// anything past the slot after capping just gets cut by the sequence end).
const fitRate = (name: SceneName, frames: number) => {
  const d = manifest.scenes[name].durationSec;
  return Math.min(2, Math.max(1, d / (frames / FPS)));
};

const soft = (frames: number) => linearTiming({ durationInFrames: frames });
const snap = (frames: number) =>
  linearTiming({
    durationInFrames: frames,
    easing: Easing.bezier(0.65, 0, 0.35, 1),
  });

export const PromoVideo: React.FC = () => {
  const { width } = useVideoConfig();
  const dm = manifest.scenes.darkmode;
  const darkStart = Math.max(
    0,
    Math.round((dm.markers.toggledAt - 0.8) * FPS)
  );
  // compare.mp4 has no markers and its slot is much shorter than the clip,
  // so fitRate's 2x cap would still land mid-typing. The clip ends on its
  // settled, most-illustrative state (populated comparison table), so anchor
  // startFrom to play the clip's tail: end of clip lines up with end of slot.
  const compareStart =
    Math.round(manifest.scenes.compare.durationSec * FPS) - SCENES.compare;
  // courses.mp4: the CS3500 page top is fully painted at ~6.6s (everything
  // earlier is the dept hop + loading fade-in) and the clip ends settled on
  // the Professors panel. Play from that first painted frame through the
  // clip end, and freeze-hold the painted top for whatever the slot has left
  // over, so the page top holds on screen instead of flashing by mid-scroll.
  const coursesPlayFrom = Math.round(6.6 * FPS);
  const coursesPlayFrames =
    Math.round(manifest.scenes.courses.durationSec * FPS) - coursesPlayFrom;
  const coursesHold = Math.max(0, SCENES.courses - coursesPlayFrames);
  return (
    <AbsoluteFill style={{ backgroundColor: DARK }}>
      <TransitionSeries>
        <TransitionSeries.Sequence durationInFrames={SCENES.intro}>
          <IntroCard />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={driftFade()} timing={soft(TRANSITIONS.search)} />
        <TransitionSeries.Sequence durationInFrames={SCENES.search}>
          <FootageScene
            src={manifest.scenes.search.file}
            playbackRate={fitRate('search', SCENES.search)}
            caption="Find any professor in seconds"
          />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={whipPan({ width })} timing={snap(TRANSITIONS.professor)} />
        <TransitionSeries.Sequence durationInFrames={SCENES.professor}>
          <FootageScene
            src={manifest.scenes.professor.file}
            playbackRate={fitRate('professor', SCENES.professor)}
            caption="Every review source. One page."
          />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={zoomThrough()} timing={snap(TRANSITIONS.ask)} />
        <TransitionSeries.Sequence durationInFrames={SCENES.ask}>
          <AskScene />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={whipPan({ width })} timing={snap(TRANSITIONS.compare)} />
        <TransitionSeries.Sequence durationInFrames={SCENES.compare}>
          <FootageScene
            src={manifest.scenes.compare.file}
            startFrom={compareStart}
            caption="Compare head-to-head"
          />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={whipPan({ width })} timing={snap(TRANSITIONS.courses)} />
        <TransitionSeries.Sequence durationInFrames={SCENES.courses}>
          <Sequence durationInFrames={coursesHold}>
            <Freeze frame={0}>
              <FootageScene
                src={manifest.scenes.courses.file}
                startFrom={coursesPlayFrom}
              />
            </Freeze>
          </Sequence>
          <Sequence from={coursesHold}>
            <FootageScene
              src={manifest.scenes.courses.file}
              startFrom={coursesPlayFrom}
            />
          </Sequence>
          <Caption text="Browse every course and department" />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={soft(TRANSITIONS.darkmode)} />
        <TransitionSeries.Sequence durationInFrames={SCENES.darkmode}>
          <FootageScene src={dm.file} startFrom={darkStart} />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={soft(TRANSITIONS.outro)} />
        <TransitionSeries.Sequence durationInFrames={SCENES.outro}>
          <OutroCard />
        </TransitionSeries.Sequence>
      </TransitionSeries>
      <Audio
        src={staticFile(MUSIC)}
        volume={(f) =>
          interpolate(
            f,
            [0, 24, TOTAL_FRAMES - 60, TOTAL_FRAMES - 6],
            [0, 1, 1, 0],
            { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
          )
        }
      />
    </AbsoluteFill>
  );
};
