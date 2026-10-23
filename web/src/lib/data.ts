// Build-time access to the exported study data (web/data) and the sigil geometry.
// Nothing here runs in the browser.
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { resolve } from 'node:path';

// Builds run from web/; bundling moves this module, so paths resolve from the working directory.
const root = (path: string) => resolve(process.cwd(), path);
const readJson = <T>(path: string): T => JSON.parse(readFileSync(root(path), 'utf8')) as T;

export type Agent = 'source' | 'native' | 'adapted';
export type Side = 'p1' | 'p2';
export type Result = 'win' | 'loss' | 'tie' | 'unfinished';

export interface BattleRow {
  id: string;
  run: string;
  game_id: string;
  agent: Agent;
  seed: number;
  generation: number;
  variant: string;
  result: Result;
  end_reason: string;
  turns: number;
  protect_uses: number;
  protect_opportunities: number;
  protect_depleted: boolean;
  candidate_team: string;
  opponent_team: string;
  candidate_side: Side;
}

export interface Mon {
  species: string;
  hp: number;
  maxhp?: number;
  fainted: boolean;
  status: string | null;
}

export interface MoveOption {
  name: string;
  pp: number | null;
  maxpp: number | null;
  disabled: boolean;
  protect: boolean;
}

export interface SlotChoice {
  slot: 'a' | 'b';
  species: string;
  moves: MoveOption[];
  chosen: { kind: string; index?: number; name?: string; species?: string };
}

export interface Frame {
  turn: number;
  field: Record<Side, (Mon | null)[]>;
  after: Record<Side, (Mon | null)[]>;
  events: string[];
  choices?: Partial<Record<Side, SlotChoice[]>>;
}

export interface Member {
  species: string;
  item: string;
  ability: string;
  moves: string[];
  stats: Record<string, number>;
}

export interface Battle {
  id: string;
  run: string;
  game_id: string;
  agent: Agent;
  seed: number;
  generation: number;
  variant: string;
  format_id: string;
  eval_seed: number;
  battle_seed: number[];
  checkpoint: string;
  simulator_revision: string;
  candidate: string;
  opponent: string;
  candidate_side: Side;
  labels: Record<Side, string>;
  teams: Record<Side, string>;
  result: Result;
  end_reason: string;
  turns: number;
  protect: { uses: number; opportunities: number; depleted: boolean };
  rosters: Partial<Record<Side, Member[]>>;
  prelude: string[];
  frames: Frame[];
}

interface Index {
  spec: string[];
  simulator_revision: string[];
  opponent: string[];
  eval_seed: number[];
  checkpoints: number;
  games: number;
  battles: BattleRow[];
}

export interface Stat {
  mean: number;
  min: number;
  max: number;
}

export interface RecoveryPoint {
  generation: number;
  seeds: Record<string, { games: number; protect_uses: number; protect_opportunities: number; protect_use_rate: number; points_per_game: number; depletion_rate: number }>;
  points_per_game: Stat;
  protect_use_rate: Stat;
  depletion_rate: Stat;
  games: number;
  protect_opportunities: number;
}

export interface Series {
  agent: Agent;
  variant: string;
  points: RecoveryPoint[];
}

export interface Sigil {
  slug: string;
  types: string[];
  colors: string[];
  points: string;
  speedTip: [number, number];
}

interface SigilSheet {
  cell: string;
  sigils: Record<string, Sigil>;
}

let index: Index | undefined;
export const study = () => (index ??= readJson<Index>('data/battles.json'));
export const battles = () => study().battles;
export const recovery = () => readJson<{ series: Series[] }>('data/recovery.json').series;
export const teams = () => readJson<{ teams: Record<string, Member[]> }>('data/teams.json').teams;
export const sigilSheet = () => readJson<SigilSheet>('design/sigils/sigils.json');

export function battle(id: string): Battle {
  return JSON.parse(gunzipSync(readFileSync(root(`data/battles/${id}.json.gz`))).toString('utf8')) as Battle;
}

export const AGENTS: Agent[] = ['source', 'native', 'adapted'];
export const AGENT_INFO: Record<Agent, { name: string; rules: string; pp: number; blurb: string }> = {
  source: {
    name: 'Source',
    rules: 'Scarlet/Violet rules',
    pp: 16,
    blurb: 'Trained with 16 Protect PP and evaluated there.',
  },
  native: {
    name: 'Native',
    rules: 'Champions rules',
    pp: 8,
    blurb: 'Trained from the heuristic with 8 Protect PP.',
  },
  adapted: {
    name: 'Adapted',
    rules: 'Source, refitted for Champions',
    pp: 8,
    blurb: 'Starts from the final Source checkpoint and keeps training with 8 Protect PP.',
  },
};

export interface SheetMember {
  species: string;
  item: string;
  ability: string;
  moves: string[];
  nature: string;
  evs: Record<string, number>;
  teraType: string;
}

export interface TeamSheet {
  id: string;
  family: string;
  split: string;
  pokemon: SheetMember[];
}

interface Manifest {
  description: string;
  splits: Record<string, string[]>;
  teams: Record<string, Omit<TeamSheet, 'id'>>;
}

export const manifest = () => readJson<Manifest>('../experiments/teams/protect-pp.json');
export const testTeams = (): TeamSheet[] =>
  manifest().splits.test.map((id) => ({ id, ...manifest().teams[id] }));

/** "test-annihilape-bulky" reads as "Annihilape bulky". */
export const teamName = (id: string) => {
  const words = id.replace(/^(test|train|val)-/, '').split('-').join(' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
};
export const agentName = (agent: Agent) => AGENT_INFO[agent].name;
export const ppCap = (variant: string) => (variant === 'protect-8' ? 8 : 16);
export const resultWord: Record<Result, string> = {
  win: 'Win',
  loss: 'Loss',
  tie: 'Tie',
  unfinished: 'Stalled',
};

/** Featured games: for each agent, the final-checkpoint game with the most Protect uses.
 *  Ties go to the lowest battle number. This rule is printed on the Study P screen. */
export function featured(): BattleRow[] {
  const finalGen = Math.max(...battles().map((b) => b.generation));
  return AGENTS.map((agent) =>
    battles()
      .filter((b) => b.agent === agent && b.generation === finalGen && b.turns > 0)
      .sort((a, b) => b.protect_uses - a.protect_uses || a.id.localeCompare(b.id))[0],
  ).filter((b): b is BattleRow => Boolean(b));
}

export function totals() {
  const rows = battles();
  const sum = (key: 'protect_uses' | 'protect_opportunities') => rows.reduce((n, r) => n + r[key], 0);
  return {
    games: rows.length,
    checkpoints: study().checkpoints,
    depleted: rows.filter((r) => r.protect_depleted).length,
    stalled: rows.filter((r) => r.end_reason === 'stalled').length,
    protectUses: sum('protect_uses'),
    protectOpportunities: sum('protect_opportunities'),
  };
}
