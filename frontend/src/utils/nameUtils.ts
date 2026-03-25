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
