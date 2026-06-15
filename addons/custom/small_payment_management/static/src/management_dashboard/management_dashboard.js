/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

// SPM Management Dashboard (report §9.1). Skeleton component.
export class SpmManagementDashboard extends Component {}
SpmManagementDashboard.template = "spm.ManagementDashboard";

registry.category("actions").add("spm_management_dashboard", SpmManagementDashboard);
