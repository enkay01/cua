import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ClefClient } from './clef_adapter.js';
import { ClefGridLocalizer } from './grid_localizer.js';

function getImageDimensions(filePath: string): { width: number; height: number } {
  const buf = fs.readFileSync(filePath);

  // PNG
  if (
    buf.length >= 24 &&
    buf[0] === 0x89 &&
    buf[1] === 0x50 &&
    buf[2] === 0x4e &&
    buf[3] === 0x47
  ) {
    const width = buf.readUInt32BE(16);
    const height = buf.readUInt32BE(20);
    return { width, height };
  }

  // JPEG
  if (buf.length >= 4 && buf[0] === 0xff && buf[1] === 0xd8) {
    let offset = 2;
    while (offset < buf.length) {
      if (buf[offset] !== 0xff) {
        offset++;
        continue;
      }
      const marker = buf[offset + 1];
      if (marker >= 0xc0 && marker <= 0xc3) {
        const height = buf.readUInt16BE(offset + 5);
        const width = buf.readUInt16BE(offset + 7);
        return { width, height };
      }
      offset += 2 + buf.readUInt16BE(offset + 2);
    }
  }

  throw new Error(`Unsupported image format or failed to read dimensions for: ${filePath}`);
}

export async function main(args: string[] = process.argv.slice(2)): Promise<void> {
  let imagePath: string | undefined;
  let prompt: string | undefined;
  let levels = 3;
  let model: string | undefined;
  let cropDesktop = false;
  const mockFixtures: string[] = [];

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--image' && i + 1 < args.length) {
      imagePath = args[++i];
    } else if (arg === '--prompt' && i + 1 < args.length) {
      prompt = args[++i];
    } else if (arg === '--levels' && i + 1 < args.length) {
      levels = parseInt(args[++i], 10);
    } else if (arg === '--model' && i + 1 < args.length) {
      model = args[++i];
    } else if (arg === '--crop-desktop') {
      cropDesktop = true;
    } else if (arg === '--mock-fixtures') {
      while (i + 1 < args.length && !args[i + 1].startsWith('--')) {
        mockFixtures.push(args[++i]);
      }
    }
  }

  if (!imagePath || !prompt) {
    console.error('Usage: tsx typescript/localizer.ts --image <path> --prompt <description> [--levels <n>] [--crop-desktop]');
    process.exit(1);
  }

  let dims = getImageDimensions(imagePath);
  if (cropDesktop) {
    dims = { width: dims.width, height: Math.max(1, dims.height - 1254) };
    console.log(`Cropped to desktop viewport: ${dims.width}x${dims.height}`);
  }

  let fixturePaths = mockFixtures;
  if (fixturePaths.length === 0 && !process.env.CLOUDFLARE_API_TOKEN) {
    const __dirname = path.dirname(fileURLToPath(import.meta.url));
    const baseFixtureDir = path.resolve(__dirname, '..', 'fixtures');
    fixturePaths = [
      path.join(baseFixtureDir, 'clef-localization-level1.json'),
      path.join(baseFixtureDir, 'clef-localization-level2.json'),
      path.join(baseFixtureDir, 'clef-localization-level3.json'),
    ];
    console.log('No Cloudflare credentials found. Using local golden fixtures for offline verification.');
  }

  const client = new ClefClient({
    model,
    mockFixturePaths: fixturePaths.length > 0 ? fixturePaths : undefined,
  });

  const localizer = new ClefGridLocalizer(client, { numLevels: levels });

  const fileBuf = fs.readFileSync(imagePath);
  console.log(`Localizing target: ${JSON.stringify(prompt)} in ${imagePath} (${dims.width}x${dims.height})...`);
  const result = await localizer.localize(
    {
      width: dims.width,
      height: dims.height,
      base64: fileBuf.toString('base64'),
    },
    prompt
  );

  console.log(`\nLocalization Result: ${result.status.toUpperCase()}`);
  for (const rec of result.iterations) {
    console.log(
      `  Level ${rec.level}: Winning Cell=${rec.winningCell} (Confidence=${rec.confidence.toFixed(3)}) | ` +
      `Crop=(${rec.cropBox.left}, ${rec.cropBox.top}, ${rec.cropBox.right}, ${rec.cropBox.bottom}) | ` +
      `Root Center=(${rec.cellGeometry.rootCenterX.toFixed(1)}, ${rec.cellGeometry.rootCenterY.toFixed(1)})`
    );
  }

  if (result.success && result.clickX !== undefined && result.clickY !== undefined) {
    console.log(`\nFinal Click Target: X=${result.clickX.toFixed(1)}, Y=${result.clickY.toFixed(1)}`);
  } else {
    console.log(`\nLocalization failed / abstained: ${result.reason}`);
  }
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
