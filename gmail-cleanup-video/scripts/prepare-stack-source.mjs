import {readFileSync, writeFileSync} from 'node:fs';
import assert from 'node:assert/strict';

const lines = readFileSync('../pyproject.toml', 'utf8').split(/\r?\n/);
assert.equal(lines[10].trim(), '"langgraph==1.2.8",', 'Update the animation if the source dependency changes');
const escape = (text) => text.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
const rows = lines.slice(8, 15).map((line, i) => `<text x="35" y="${124 + i * 45}" fill="#637994" font-size="19">${i + 9}</text><text x="90" y="${124 + i * 45}" fill="${i === 2 ? '#ffd086' : '#cad7e9'}" font-size="26">${escape(line)}</text>`).join('');
writeFileSync('public/stack-source.svg', `<svg xmlns="http://www.w3.org/2000/svg" width="1160" height="450" viewBox="0 0 1160 450"><rect width="1160" height="450" rx="16" fill="#101e30"/><path d="M0 67h1160" stroke="#354960"/><g font-family="Consolas, monospace"><text x="34" y="43" font-size="22" fill="#a8bdd6">pyproject.toml / actual source excerpt</text><rect x="20" y="185" width="1120" height="45" rx="6" fill="#3b3021"/><path d="M20 185v45" stroke="#ffd086" stroke-width="4"/>${rows}</g></svg>`);
console.log('Verified langgraph==1.2.8 at line 11; generated exact source excerpt (lines 9-15).');
