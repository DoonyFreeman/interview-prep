/** Only authored, local lesson-section links can display a concept preview. */
export function isConceptLink(href: string | undefined, title: string | undefined): boolean {
  if (!href || !title?.trim()) return false;
  return /^\/courses\/[a-z0-9]+(?:-[a-z0-9]+)*\/lessons\/[a-z0-9]+(?:-[a-z0-9]+)*#[^\s#?]+$/u.test(href);
}
