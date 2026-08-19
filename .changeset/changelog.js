"use strict";

/** Keep a Changelog bullets; section headers are rewritten by scripts/format_changelog.py */
async function getReleaseLine(changeset) {
  const summary = changeset.summary.trim();
  if (!summary) {
    return "";
  }
  const lines = summary.split("\n");
  const first = lines[0].replace(/^[-*]\s*/, "");
  let out = `- ${first}`;
  if (lines.length > 1) {
    out += `\n${lines.slice(1).join("\n")}`;
  }
  return `\n${out}`;
}

async function getDependencyReleaseLine() {
  return "";
}

module.exports = {
  getReleaseLine,
  getDependencyReleaseLine,
};
