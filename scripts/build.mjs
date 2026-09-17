import { readFile, writeFile, mkdir } from "node:fs/promises";
const files = ["src/calculations.js", "src/editor.js", "src/ev-savings-card.js"];
const sources = await Promise.all(files.map(file => readFile(file, "utf8")));
const bundle = sources.map(source => source.replace(/^import .*;\n/gm, "").replace(/^export /gm, "")).join("\n");
await mkdir("dist", { recursive: true });
await writeFile("dist/ev-savings-card.js", `// EV Savings Card — MIT License\n${bundle}`);
console.log("Built dist/ev-savings-card.js");

await mkdir("custom_components/ev_savings/www", { recursive: true });
await writeFile("custom_components/ev_savings/www/ev-savings-card.js", `// EV Savings Card — MIT License\n${bundle}`);
