export function formatDateTime(value: string | null) {
  if (!value) {
    return "未记录";
  }

  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function formatNumber(value: number | string) {
  if (typeof value === "string") {
    return value;
  }

  return new Intl.NumberFormat("zh-CN").format(value);
}

export function formatPercent(value: number, digits = 0) {
  if (!Number.isFinite(value)) {
    return "--";
  }

  return `${Math.max(0, value).toFixed(digits)}%`;
}

export function healthLabel(status: string) {
  const mapping: Record<string, string> = {
    healthy: "健康",
    warning: "告警",
    failing: "失败",
    unknown: "未知",
    success: "成功",
    failed: "失败",
    no_new_content: "无新增",
  };

  return mapping[status] || status;
}

export function formatHost(url: string) {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}

export function formatUptime(seconds: number | null | undefined) {
  if (!seconds || seconds < 0) {
    return "未记录";
  }

  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  if (days > 0) {
    return `${days} 天 ${hours} 小时`;
  }
  if (hours > 0) {
    return `${hours} 小时 ${minutes} 分`;
  }
  return `${minutes} 分`;
}

export function formatShortDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(value));
}
