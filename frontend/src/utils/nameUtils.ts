export function splitProfName(name: string, maxFirst = 19): [string, string] {
  if (name.length <= maxFirst) return [name, ''];
  let splitIdx = -1;
  let splitChar = '';
  for (let i = Math.min(maxFirst, name.length - 1); i >= 0; i--) {
    if (name[i] === ' ' || name[i] === '-') {
      splitIdx = i;
      splitChar = name[i];
      break;
    }
  }
  if (splitIdx === -1) return [name, ''];
  if (splitChar === '-') return [name.slice(0, splitIdx + 1), name.slice(splitIdx + 1)];
  return [name.slice(0, splitIdx), name.slice(splitIdx + 1)];
}

export function stripPrefix(name: string): string {
  return name.replace(/^(Dr\.|Prof\.|Professor|Mr\.|Ms\.|Mrs\.|Mx\.)\s+/i, '').trim();
}

export function getInitials(name: string): string {
  return stripPrefix(name)
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('');
}
