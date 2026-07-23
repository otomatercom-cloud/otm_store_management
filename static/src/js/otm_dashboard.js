/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { Component, onWillStart, onMounted, onWillUnmount, useState } from "@odoo/owl";

class OtmStoreDashboard extends Component {
    static template = "otm_store_management.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.userName = user.name;
        this.state = useState({
            loading: true,
            navOpen: false,
            cards: {},
            lowStockItems: [],
            stores: [],
            departmentConsumption: [],
            storeWiseStock: [],
            monthlyPurchaseValue: 0,
            monthlyConsumptionValue: 0,
        });

        this._onKeydown = (ev) => {
            if (ev.key === "Escape") {
                this.closeNav();
            }
        };
        onMounted(() => document.addEventListener("keydown", this._onKeydown));
        onWillUnmount(() => document.removeEventListener("keydown", this._onKeydown));

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        this.state.loading = true;
        const data = await this.orm.call("otm.dashboard", "get_dashboard_data", [[]]);
        this.state.cards = data.cards;
        this.state.lowStockItems = data.low_stock_items;
        this.state.stores = data.stores;
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

    // --- low stock gauge helpers ---
    gaugeCap(item) {
        // fall back to a sensible ceiling when max_qty isn't configured,
        // so the bar never divides by zero or looks empty.
        return item.max_qty > 0 ? item.max_qty : Math.max(item.reorder_qty * 2, item.current_qty, 1);
    }

    gaugeFillWidth(item) {
        const cap = this.gaugeCap(item);
        const pct = Math.min((item.current_qty / cap) * 100, 100);
        return Math.max(pct, 0) + "%";
    }

    gaugeReorderPosition(item) {
        const cap = this.gaugeCap(item);
        return Math.min((item.reorder_qty / cap) * 100, 100) + "%";
    }

    gaugeIsCritical(item) {
        return item.status === 'out' || item.status === 'critical';
    }

    isStockOut(item) {
        return item.status === 'out';
    }

    coverLabel(item) {
        if (item.days_of_cover === null || item.days_of_cover === false) {
            return "—";
        }
        return item.days_of_cover < 1 ? "<1" : Math.round(item.days_of_cover);
    }

    // --- store cards ---
    storeAccent(store) {
        if (store.out_count > 0) return "out";
        if (store.critical_count > 0) return "critical";
        if (store.low_count > 0) return "low";
        return "ok";
    }

    openStoreDetail(store) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: store.name + " — Live Stock",
            res_model: "otm.stock.quant",
            views: [[false, "list"], [false, "pivot"]],
            domain: [["store_id", "=", store.id]],
            context: { search_default_group_product: 1 },
            target: "current",
        });
    }

    onOpenStores() {
        this.action.doAction("otm_store_management.action_otm_store");
    }

    onOpenProducts() {
        this.action.doAction("otm_store_management.action_otm_product");
    }

    onAddProduct() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "product.template",
            views: [[false, "form"]],
            target: "current",
            context: { default_type: "consu", default_is_storable: true },
        });
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

    // --- sidebar ---
    navigate(actionXmlId) {
        this.state.navOpen = false;
        this.action.doAction("otm_store_management." + actionXmlId);
    }

    toggleNav() {
        this.state.navOpen = !this.state.navOpen;
    }

    closeNav() {
        this.state.navOpen = false;
    }
}

registry.category("actions").add("otm_store_dashboard", OtmStoreDashboard);
