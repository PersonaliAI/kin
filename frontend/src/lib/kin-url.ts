// In the Kin app itself, links are same-origin — kinUrl is just the path.
export function kinUrl(path: string = "/dashboard"): string {
  return path;
}
