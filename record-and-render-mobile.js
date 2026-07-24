const { execFileSync } = require('child_process');
const path = require('path');

const root = __dirname;
const rawCapture = path.join(root, 'output', 'repfind-mobile-screen-recording.webm');
const deliveryMp4 = path.join(root, 'output', 'repfind-mobile-screen-recording.mp4');

function run(command, args) {
  execFileSync(command, args, { cwd: root, stdio: 'inherit' });
}

try {
  // The raw capture matches the 360×640 browser viewport exactly. Scaling happens only after capture,
  // which prevents a small page from being placed in the top-left of a 1080×1920 recording canvas.
  run(process.execPath, [path.join(root, 'record-screen-demo-mobile.js')]);
  run('ffmpeg', [
    '-y',
    '-i', rawCapture,
    '-an',
    '-vf', 'scale=1080:1920:flags=lanczos',
    '-c:v', 'libx264',
    '-preset', 'medium',
    '-crf', '20',
    '-pix_fmt', 'yuv420p',
    '-movflags', '+faststart',
    deliveryMp4
  ]);
  console.log(`\nPortrait MP4 written to: ${deliveryMp4}`);
} catch (error) {
  console.error(error.message || error);
  process.exitCode = 1;
}
