import { driver, type DriveStep } from 'driver.js';
import 'driver.js/dist/driver.css';

const SEEN_KEY = 'onboarding:v1:seen';

const steps: DriveStep[] = [
  {
    popover: {
      title: 'Welcome to the builder',
      description:
        'Strategies are built by dragging blocks and wiring them together. This 30-second tour shows where everything lives.',
      side: 'over',
      align: 'center',
    },
  },
  {
    element: '[data-tour="palette"]',
    popover: {
      title: 'Blocks & templates',
      description:
        'Every building block lives here — triggers, indicators, fundamentals, math, conditions, orders, risk exits. Drag one onto the canvas, or click a <strong>Template</strong> at the top to load a ready-made strategy.',
      side: 'right',
      align: 'start',
    },
  },
  {
    element: '[data-tour="canvas"]',
    popover: {
      title: 'The canvas',
      description:
        'Blocks live on the canvas. Drag from a block\'s output port to another block\'s input port to connect them. Data flows left-to-right, from triggers through indicators into orders.',
      side: 'top',
      align: 'center',
    },
  },
  {
    element: '[data-tour="inspector"]',
    popover: {
      title: 'Inspector',
      description:
        'Click any block on the canvas to see and edit its parameters here — SMA period, RSI thresholds, stop-loss percent, etc.',
      side: 'left',
      align: 'start',
    },
  },
  {
    element: '[data-tour="run"]',
    popover: {
      title: 'Run your backtest',
      description:
        'Once the graph is complete and valid, hit <strong>Run</strong>. You can also use <strong>Sweep</strong> to test many parameter values at once. Need the full reference? Check <a href="/app/docs" target="_blank" style="color:#2563eb;text-decoration:underline">Docs</a>. You can replay this tour from Settings.',
      side: 'left',
      align: 'end',
    },
  },
];

export function hasSeenTour(): boolean {
  if (typeof window === 'undefined') return true;
  return localStorage.getItem(SEEN_KEY) === 'true';
}

export function markTourSeen(): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(SEEN_KEY, 'true');
}

export function resetTour(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(SEEN_KEY);
}

export function startTour(): void {
  const d = driver({
    showProgress: true,
    allowClose: true,
    overlayOpacity: 0.55,
    popoverClass: 'fyp-driver-popover',
    nextBtnText: 'Next →',
    prevBtnText: '← Back',
    doneBtnText: 'Got it',
    onDestroyed: markTourSeen,
    steps,
  });
  d.drive();
}

export function startTourIfUnseen(): void {
  if (hasSeenTour()) return;
  // Defer one frame so the target DOM nodes are mounted before Driver queries them.
  requestAnimationFrame(() => startTour());
}
