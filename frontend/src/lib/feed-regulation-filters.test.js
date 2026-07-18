import test from "node:test";
import assert from "node:assert/strict";

import {
  getRegulationAcknowledgementDepartments,
  isCompanyAcknowledgementRegulation,
  regulationMatchesAcknowledgementSource,
} from "./feed-regulation-filters.ts";

const accounting = { id: 10, name: "Бухгалтерия" };
const procurement = { id: 20, name: "Закупки" };

test("selective regulations are filtered by acknowledgement departments, not access departments", () => {
  const regulation = {
    sent_to_all: false,
    departments: [accounting],
    acknowledgement_required: true,
    acknowledgement_for_all: false,
    acknowledgement_departments: [procurement],
  };

  assert.equal(regulationMatchesAcknowledgementSource(regulation, "department:10"), false);
  assert.equal(regulationMatchesAcknowledgementSource(regulation, "department:20"), true);
  assert.equal(regulationMatchesAcknowledgementSource(regulation, "company"), false);
});

test("selective acknowledgement does not become company-wide because access is company-wide", () => {
  const regulation = {
    sent_to_all: true,
    acknowledgement_required: true,
    acknowledgement_for_all: false,
    acknowledgement_departments: [accounting],
  };

  assert.equal(isCompanyAcknowledgementRegulation(regulation), false);
  assert.equal(regulationMatchesAcknowledgementSource(regulation, "department:10"), true);
});

test("all-access acknowledgement inherits departments from a selectively available document", () => {
  const regulation = {
    sent_to_all: false,
    departments: [accounting],
    acknowledgement_required: true,
    acknowledgement_for_all: true,
    acknowledgement_departments: [procurement],
  };

  assert.deepEqual(getRegulationAcknowledgementDepartments(regulation), [accounting]);
  assert.equal(regulationMatchesAcknowledgementSource(regulation, "department:10"), true);
  assert.equal(regulationMatchesAcknowledgementSource(regulation, "department:20"), false);
});

test("company acknowledgement is based on acknowledgement mode and company access together", () => {
  const regulation = {
    sent_to_all: true,
    acknowledgement_required: true,
    acknowledgement_for_all: true,
  };

  assert.equal(isCompanyAcknowledgementRegulation(regulation), true);
  assert.equal(regulationMatchesAcknowledgementSource(regulation, "company"), true);
});

test("regulations without acknowledgement stay in all regulations but not in audience filters", () => {
  const regulation = {
    sent_to_all: true,
    departments: [accounting],
    acknowledgement_required: false,
    acknowledgement_for_all: true,
    acknowledgement_departments: [accounting],
  };

  assert.equal(regulationMatchesAcknowledgementSource(regulation, "all"), true);
  assert.equal(regulationMatchesAcknowledgementSource(regulation, "company"), false);
  assert.equal(regulationMatchesAcknowledgementSource(regulation, "department:10"), false);
});
