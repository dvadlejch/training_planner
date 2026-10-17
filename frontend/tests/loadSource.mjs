import { existsSync, readFileSync } from "node:fs";
import ts from "typescript";

const urls = new Map();

/** Compile project TS/TSX into importable modules using the existing compiler. */
export function sourceUrl(path) {
  let url = path instanceof URL ? path : new URL(path, import.meta.url);
  if (!/\.tsx?$/.test(url.pathname)) {
    url = [".ts", ".tsx"].map((ext) => new URL(`${url.href}${ext}`)).find(existsSync);
  }
  if (!url) throw new Error(`Cannot resolve ${path}`);
  if (urls.has(url.href)) return urls.get(url.href);
  const { outputText } = ts.transpileModule(readFileSync(url, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.ESNext, jsx: ts.JsxEmit.ReactJSX },
    fileName: url.pathname,
  });
  const code = outputText.replace(/from (["'])([^"']+)\1/g, (_, _quote, specifier) => {
    const resolved = specifier.startsWith(".")
      ? sourceUrl(new URL(specifier, url)) : import.meta.resolve(specifier);
    return `from ${JSON.stringify(resolved)}`;
  });
  const result = `data:text/javascript;base64,${Buffer.from(code).toString("base64")}`;
  urls.set(url.href, result);
  return result;
}
