import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { execSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Output path for replacements JSON
const outPath = path.resolve(__dirname, '../../../translations/patches/cli/gemini/qwen.replacements.json');

function findQwenZhPath() {
    const candidates = [
        'D:\\Program Files\\nvm\\v22.17.1\\node_modules\\@qwen-code\\qwen-code\\locales\\zh.js'
    ];

    try {
        const npmRoot = execSync('npm root -g', { encoding: 'utf-8' }).trim();
        if (npmRoot) {
            candidates.push(path.join(npmRoot, '@qwen-code/qwen-code/locales/zh.js'));
        }
    } catch (e) {
        // ignore
    }

    // Windows standard paths
    const appData = process.env.APPDATA;
    if (appData) {
        candidates.push(path.join(appData, 'npm/node_modules/@qwen-code/qwen-code/locales/zh.js'));
    }
    
    candidates.push('C:\\Program Files\\nodejs\\node_modules\\@qwen-code\\qwen-code\\locales\\zh.js');

    for (const candidate of candidates) {
        if (fs.existsSync(candidate)) {
            console.log(`Found qwen-cli locales at: ${candidate}`);
            return candidate;
        }
    }
    return null;
}

async function main() {
    try {
        const qwenZhPath = findQwenZhPath();
        if (!qwenZhPath) {
            console.log('qwen-cli locales (zh.js) not found. Skipping extraction and keeping existing dictionary.');
            return;
        }

        // Dynamically import the ES Module using pathToFileURL to handle spaces
        const qwenLocales = await import(pathToFileURL(qwenZhPath).href);
        const dict = qwenLocales.default;

        const replacements = [];

        for (const [key, value] of Object.entries(dict)) {
            // Skip empty or trivial entries
            if (!key || !value || key === value || typeof value !== 'string' || typeof key !== 'string') {
                continue;
            }

            let finalValue = value;
            finalValue = finalValue.replace(/Qwen Code/g, 'Gemini Code');
            finalValue = finalValue.replace(/Qwen/g, 'Gemini');
            finalValue = finalValue.replace(/qwen/gi, 'gemini');

            let finalKey = key;
            finalKey = finalKey.replace(/Qwen Code/g, 'Gemini Code');
            finalKey = finalKey.replace(/Qwen/g, 'Gemini');
            finalKey = finalKey.replace(/qwen/gi, 'gemini');
            
            replacements.push([finalKey, finalValue]);
        }

        // Sort by key length descending to avoid nested replacement issues
        replacements.sort((a, b) => b[0].length - a[0].length);

        fs.writeFileSync(outPath, JSON.stringify(replacements, null, 4), 'utf-8');
        console.log(`Successfully extracted ${replacements.length} translations to ${outPath}`);
    } catch (err) {
        console.error('Error extracting dictionary:', err);
    }
}

main();
