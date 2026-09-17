export function parseTariff(config, state) {
    if (!state) {
      throw new Error(`Rate entity ${config.rate_entity} was not found`);
    }

    if (["unknown", "unavailable"].includes(state.state)) throw new Error("Tariff entity is unavailable");
    const a = state.attributes || {};

    const structure =
      a.energyratestructure ||
      a.energy_rate_structure ||
      a.rate_structure;

    const weekday =
      a.energyweekdayschedule ||
      a.energy_weekday_schedule ||
      a.weekday_schedule;

    const weekend =
      a.energyweekendschedule ||
      a.energy_weekend_schedule ||
      a.weekend_schedule;

    if (
      !Array.isArray(structure) ||
      !Array.isArray(weekday) ||
      !Array.isArray(weekend)
    ) {
      throw new Error(
        `Rate entity ${config.rate_entity} is missing OpenEI energy rate attributes`
      );
    }

    if (weekday.length !== 12 || weekend.length !== 12) {
      throw new Error("OpenEI rate schedules must contain 12 monthly arrays");
    }

    for (const schedule of [weekday, weekend]) {
      if (schedule.some(month => !Array.isArray(month) || month.length !== 24 || month.some(index => !Number.isInteger(index) || index < 0 || index >= structure.length))) {
        throw new Error("Each tariff month must contain 24 valid zero based period indexes");
      }
    }
    const periods = structure.map((tier, index) => {
      const first = Array.isArray(tier) ? tier[0] : tier;
      if (Array.isArray(tier) && tier.length !== 1) throw new Error("Tiered tariffs are not supported");
      if (first?.unit && first.unit !== "kWh") throw new Error("Tariff rates must use kWh");
      if (first?.rate == null || first.rate === "" || !Number.isFinite(Number(first.rate)) || (first.adj != null && !Number.isFinite(Number(first.adj)))) throw new Error("Tariff contains a missing or invalid rate");
      const baseRate = Number(first.rate);
      const adjustment = Number(first?.adj || 0);
      const subtotalRate =
        baseRate +
        (config.include_adjustments === false ? 0 : adjustment);

      const multiplier = Number(config.rate_multiplier ?? 1);
      const addition = Number(config.rate_addition ?? 0);

      const effectiveRate =
        subtotalRate *
          (Number.isFinite(multiplier) ? multiplier : 1) +
        (Number.isFinite(addition) ? addition : 0);

      return {
        index,
        baseRate,
        adjustment,
        effectiveRate,
        unit: first?.unit || "kWh",
        raw: first || {},
      };
    });

    if (!periods.length) {
      throw new Error("OpenEI energy rate structure contains no periods");
    }

    // URDB schedules store zero based indexes into energyratestructure.
    // If the user supplies explicit roles, use them. Otherwise infer by price:
    // lowest = discount, highest = on peak, middle = off peak.
    const roles = config.period_roles || {};

    const byIndex = (value) => {
      if (value === undefined) return undefined;
      const index = Number(value);
      if (value === null || value === "" || !Number.isInteger(index) || !periods[index]) throw new Error("Invalid period_roles index");
      return Number.isInteger(index) ? periods[index] : undefined;
    };

    const ranked = [...periods].sort(
      (x, y) => x.effectiveRate - y.effectiveRate
    );

    const discount =
      byIndex(roles.discount) ||
      ranked[0];

    const peak =
      byIndex(roles.peak) ||
      ranked[ranked.length - 1];

    let offPeak = byIndex(roles.off_peak);

    if (!offPeak) {
      if (ranked.length === 1) {
        offPeak = ranked[0];
      } else if (ranked.length === 2) {
        offPeak = ranked[0];
      } else {
        offPeak = ranked[Math.floor((ranked.length - 1) / 2)];
      }
    }

    const names = {};
    for (const p of periods) names[p.index] = `Period ${p.index + 1}`;
    if (discount) names[discount.index] = "Discount";
    if (offPeak && offPeak.index !== discount?.index) names[offPeak.index] = "Off peak";
    if (
      peak &&
      peak.index !== discount?.index &&
      peak.index !== offPeak?.index
    ) {
      names[peak.index] = "On peak";
    }

    return {
      structure,
      weekday,
      weekend,
      periods,
      names,
      discount,
      offPeak,
      peak,
      utility: a.utility || "",
      name: a.name || state.state || "",
      label: a.label || a.urdb_id || "",
      source: a.source || "OpenEI",
      startdate: a.startdate,
      enddate: a.enddate,
      rateMultiplier: Number(config.rate_multiplier ?? 1),
      rateAddition: Number(config.rate_addition ?? 0),
    };
  }


export function addEnergy(config, day, date, kwh, tariff) {
    const monthIndex = date.getMonth();
    const hour = date.getHours();
    const isWeekend =
      date.getDay() === 0 || date.getDay() === 6;

    const schedule = isWeekend
      ? tariff.weekend
      : tariff.weekday;

    const periodIndex = Number(
      schedule?.[monthIndex]?.[hour]
    );

    const period = tariff.periods[periodIndex];

    if (!period) {
      throw new Error(
        `OpenEI schedule references missing energy period ${periodIndex}`
      );
    }

    let comparison = tariff.offPeak;

    if (config.comparison_period === "peak") {
      comparison = tariff.peak;
    } else if (config.comparison_period === "discount") {
      comparison = tariff.discount;
    }

    if (!comparison) comparison = tariff.offPeak || tariff.periods[0];

    const actual = kwh * period.effectiveRate;
    const compared = kwh * comparison.effectiveRate;

    day.kwh += kwh;
    day.actualCost += actual;
    day.comparisonCost += compared;
    day.periodKwh[periodIndex] =
      (day.periodKwh[periodIndex] || 0) + kwh;

    if (periodIndex === tariff.discount?.index) {
      day.discountKwh += kwh;
    } else if (periodIndex === tariff.peak?.index) {
      day.peakKwh += kwh;
    } else {
      day.offPeakKwh += kwh;
    }
  }
