import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it, vi } from "vitest";
import { PrivateOpenspecDownloads } from "./PrivateOpenspecDownloads";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));

it("only shows downloads available to the current session", () => {
  const client = new QueryClient();
  const render = (token: string | null) => renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <PrivateOpenspecDownloads token={token} />
    </QueryClientProvider>,
  );
  const set = (token: string, original: boolean, bundle: boolean) =>
    client.setQueryData(["private-openspec", token], { original, bundle });
  set("owner", true, true);
  const owner = render("owner");
  expect(owner).toContain("cheatsheets.downloadOpenspec");
  expect(owner).toContain("cheatsheets.downloadMyBundle");
  expect(render("other")).toBe(""); // Before resolving the new session; no previous data.
  set("other", false, false);
  expect(render("other")).toBe("");
  expect(render(null)).toBe("");
  set("owner", true, false);
  expect(render("owner")).toContain("cheatsheets.downloadOpenspec");
  expect(render("owner")).not.toContain("cheatsheets.downloadMyBundle");
  set("owner", false, true);
  expect(render("owner")).not.toContain("cheatsheets.downloadOpenspec");
  expect(render("owner")).toContain("cheatsheets.downloadMyBundle");
  client.clear();
});
