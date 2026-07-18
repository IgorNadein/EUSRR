export type RegulationSourceFilter = "all" | "company" | `department:${number}`;

type RegulationDepartment = {
  id: number;
  name: string;
};

type RegulationAudience = {
  sent_to_all?: boolean;
  departments?: RegulationDepartment[];
  acknowledgement_required?: boolean;
  acknowledgement_for_all?: boolean;
  acknowledgement_departments?: RegulationDepartment[];
};

export function isCompanyAcknowledgementRegulation(document: RegulationAudience) {
  return Boolean(
    document.acknowledgement_required
      && document.acknowledgement_for_all
      && document.sent_to_all,
  );
}

export function getRegulationAcknowledgementDepartments(
  document: RegulationAudience,
): RegulationDepartment[] {
  if (!document.acknowledgement_required) return [];

  if (document.acknowledgement_for_all) {
    return document.sent_to_all ? [] : (document.departments || []);
  }

  return document.acknowledgement_departments || [];
}

export function regulationMatchesAcknowledgementSource(
  document: RegulationAudience,
  source: RegulationSourceFilter,
) {
  if (source === "all") return true;
  if (source === "company") return isCompanyAcknowledgementRegulation(document);

  const departmentId = Number(source.split(":")[1]);
  return getRegulationAcknowledgementDepartments(document).some(
    (department) => department.id === departmentId,
  );
}
