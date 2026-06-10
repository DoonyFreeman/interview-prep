// Rasterise public/favicon.svg into the PNG sizes browsers / iOS / PWA want.
// Run with: node scripts/gen-icons.mjs
import { Resvg } from "@resvg/resvg-js";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const svg = readFileSync(join(root, "public/favicon.svg"));

const targets = [
  ["favicon-32.png", 32],
  ["favicon-48.png", 48],
  ["apple-touch-icon.png", 180],
  ["icon-192.png", 192],
  ["icon-512.png", 512],
];

for (const [name, size] of targets) {
  const png = new Resvg(svg, { fitTo: { mode: "width", value: size } })
    .render()
    .asPng();
  writeFileSync(join(root, "public", name), png);
  console.log(`${name} (${size}px) ${png.length} bytes`);
}
