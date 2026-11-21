const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const readline = require('node:readline');

const emit = data => process.stdout.write(`${JSON.stringify(data)}\n`);
const appData = process.env.APPDATA;
if (appData) require('dotenv').config({ path: path.join(appData, 'opencluely', '.env'), quiet: true });
if (process.platform === 'darwin') require('dotenv').config({ path: path.join(os.homedir(), 'Library', 'Application Support', 'opencluely', '.env'), quiet: true });
const llm = require('./src/services/llm.service');
const config = require('./src/core/config');
const project = fs.readFileSync(path.join(__dirname, 'prompts', 'scam-drift.md'), 'utf8');
config.set('llm.gemini.maxRetries', 1);
config.set('llm.gemini.timeout', 3200);
config.set('llm.gemini.fallbackModels', config.get('llm.gemini.fallbackModels').slice(0, 1));

// Use the installed OpenCluely provider, including its model selection and streaming parser.
// The direct streaming method keeps this request out of the DSA prompt and chat history.
const input = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
let busy = false;
input.on('line', async line => {
  let request;
  try { request = JSON.parse(line); } catch { return; }
  const { id, question } = request || {};
  if (!Number.isSafeInteger(id)) return;
  if (typeof question !== 'string' || !question.trim() || question.length > 1200) {
    emit({ id, error: 'Enter a question between 1 and 1,200 characters.' });
    return;
  }
  if (!llm.isInitialized) { emit({ id, error: 'Add a Gemini key to generate answers.' }); return; }
  if (busy) { emit({ id, error: 'OpenCluely is finishing another answer.' }); return; }
  busy = true;
  try {
    const body = {
      systemInstruction: { parts: [{ text: project }] },
      contents: [{ role: 'user', parts: [{ text: question }] }],
      generationConfig: llm.getGenerationConfig({ temperature: 0.2, maxOutputTokens: 192 }),
    };
    const response = await llm.executeStreamingRequest(body, delta => emit({ id, delta }));
    emit({ id, response });
  } catch {
    emit({ id, error: 'OpenCluely could not generate an answer. Use the prepared answer.' });
  } finally {
    busy = false;
  }
});
