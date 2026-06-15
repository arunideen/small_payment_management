/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

// SPM "My Wallet" individual dashboard (report §9.2). Skeleton component.
export class SpmMyWallet extends Component {}
SpmMyWallet.template = "spm.MyWallet";

registry.category("actions").add("spm_my_wallet", SpmMyWallet);
