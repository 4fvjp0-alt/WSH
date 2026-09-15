/** Loads the baked world from disk so the simulation can be tested headlessly. */
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { World, loadWorld, type WorldMeta } from '../src/core/world/worldData.ts';

const dataDir = join(dirname(fileURLToPath(import.meta.url)), '..', 'public', 'data');

export async function loadWorldFromDisk(): Promise<World> {
  return loadWorld(
    async (name) => {
      const buf = await readFile(join(dataDir, name));
      return buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) as ArrayBuffer;
    },
    async (name) => JSON.parse(await readFile(join(dataDir, name), 'utf8')) as WorldMeta,
  );
}
