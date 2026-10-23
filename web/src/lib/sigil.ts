// Sigil geometry shared by the server render and the battle script.
export interface SigilShape {
  points: string;
  colors: string[];
  speedTip: [number, number];
}

export const CELL = '60,12 101.57,36 101.57,84 60,108 18.43,84 18.43,36';
export const AXES: [number, number, number, number][] = [
  [60, 12, 60, 108],
  [101.57, 36, 18.43, 84],
  [101.57, 84, 18.43, 36],
];

/** Species names in logs carry formes ("Urshifu-Rapid-Strike"); the sigil sheet keys them by name. */
export const sigilKey = (species: string) => species;
