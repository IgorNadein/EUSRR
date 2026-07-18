import test from "node:test";
import assert from "node:assert/strict";

import { canPreviewDocument, getDocumentFileExtension } from "./document-preview.ts";

test("document preview capabilities stay consistent across document surfaces", () => {
  assert.equal(getDocumentFileExtension("policy.final.PDF?download=1"), "pdf");
  assert.equal(canPreviewDocument("policy.pdf"), true);
  assert.equal(canPreviewDocument("instructions.docx"), true);
  assert.equal(canPreviewDocument("README"), true);
  assert.equal(canPreviewDocument("archive.zip"), false);
});
