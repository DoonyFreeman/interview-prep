import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ReactNode } from "react";
import { slugify } from "../lib/slugify";
import { ShikiCode } from "./ShikiCode";

/** Flatten a React children tree to plain text (for computing heading ids). */
function nodeText(node: ReactNode): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(nodeText).join("");
  if (typeof node === "object" && "props" in node) {
    return nodeText((node as { props: { children?: ReactNode } }).props.children);
  }
  return "";
}

function heading(level: 1 | 2 | 3) {
  const Tag = `h${level}` as "h1" | "h2" | "h3";
  return function Heading({ children }: { children?: ReactNode }) {
    return <Tag id={slugify(nodeText(children))}>{children}</Tag>;
  };
}

export function Markdown({ markdown }: { markdown: string }) {
  return (
    <div className="prose max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: heading(1),
          h2: heading(2),
          h3: heading(3),
          a({ href, children }) {
            const external = href?.startsWith("http");
            return (
              <a
                href={href}
                {...(external
                  ? { target: "_blank", rel: "noreferrer" }
                  : {})}
              >
                {children}
              </a>
            );
          },
          code({ className, children }) {
            const match = /language-(\w+)/.exec(className ?? "");
            const text = String(children ?? "").replace(/\n$/, "");
            const isBlock = !!match || text.includes("\n");
            if (isBlock) {
              return <ShikiCode code={text} lang={match?.[1] ?? "text"} />;
            }
            return <code>{children}</code>;
          },
          // The block is rendered fully by ShikiCode/code, so `pre` is a passthrough.
          pre({ children }) {
            return <>{children}</>;
          },
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
