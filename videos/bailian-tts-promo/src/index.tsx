import React from 'react';
import {registerRoot,Composition} from 'remotion';
import {Main} from './Main';
import {TOTAL,FPS} from './timeline';
registerRoot(()=> <Composition id="BailianPromo" component={Main} durationInFrames={TOTAL} fps={FPS} width={1920} height={1080}/>);
