/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { Component, onWillStart, useState } from "@odoo/owl";

class OtmStoreDashboard extends Component {
    static template = "otm_store_management.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.userName = user.name;
        this.state = useState({
            loading: true,
            cards: {},
            departmentConsumption: [],
            storeWiseStock: [],
            monthlyPurchaseValue: 0,
            monthlyConsumptionValue: 0,
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        this.state.loading = true;
        const data = await this.orm.call("otm.dashboard", "get_dashboard_data", [[]]);
        this.state.cards = data.cards;
        this.state.departmentConsumption = data.department_consumption;
        this.state.storeWiseStock = data.store_wise_stock;
        this.state.monthlyPurchaseValue = data.monthly_purchase_value;
        this.state.monthlyConsumptionValue = data.monthly_consumption_value;
        this.state.loading = false;
    }

    maxValue(list) {
        if (!list || !list.length) {
            return 1;
        }
        return Math.max(...list.map((item) => item.value), 1);
    }

    barWidth(value, list) {
        const max = this.maxValue(list);
        return Math.round((value / max) * 100) + "%";
    }

    onOpenStores() {
        this.action.doAction("otm_store_management.action_otm_store");
    }

    onOpenLowStock() {
        this.action.doAction("otm_store_management.action_otm_stock_quant");
    }

    onOpenExpiry() {
        this.action.doAction("otm_store_management.action_otm_product_batch");
    }

    onOpenLedger() {
        this.action.doAction("otm_store_management.action_otm_stock_move");
    }
}

registry.category("actions").add("otm_store_dashboard", OtmStoreDashboard);
