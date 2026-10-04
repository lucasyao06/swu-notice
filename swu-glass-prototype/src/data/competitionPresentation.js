// Diagnostics remain in source metadata and the maintenance report.
export const referenceLabel = value => (value || '').replaceAll('截图参考分值', '参考分值');
export const recognitionNote = value => (value || '').replace('当前学院截图未列名', '当前学院的赛事认定待确认');
export const restrictionNote = value => (value || '')
 .replace('截图列明非数学类；公告同时包含数学类时请按原文核对参赛组别。', '仅适用于非数学类；报名时请核对公告中的参赛组别。')
 .replace('仅国赛联赛加分；依据西南大学发布的联赛通知定位官网，名称变化不代表分值规则已更新。', '仅国赛联赛加分。');

export function sourceMessage(item) {
 const error = item?.error || item?.pending_reason || '';
 if (!error) return '';
 if (item.status === '正常') return item.notice_count === 0 || /最近365天.*未保存/.test(error)
  ? '最近一年未找到可确认的对应赛事公告。' : '部分官方公告暂时无法获取，请打开官方页面查看。';
 if (/robots|禁止抓取|禁止访问/i.test(error)) return '官网不允许自动获取此栏目，请通过官方页面查看公告。';
 if (/certificate|SSL|TLS|EOF/i.test(error)) return '官网安全连接异常，暂时无法获取公告。';
 if (/timeout|timed out|超时/i.test(error)) return '官网响应超时，请稍后重试。';
 if (/HTTP|502|483|连接|Connection|远程主机/i.test(error)) return '官网暂时无法访问，请稍后重试或打开官方页面。';
 if (/维护/.test(error)) return '官网维护中，暂时无法获取公告，请稍后重试。';
 if (item.status === '解析受限' || /JavaScript|JS|动态|接口|非标准端口/i.test(error)) return '官方公告暂时无法自动获取，请打开官方页面查看。';
 if (/身份|同一|全名|同名|名称|主办方|赛种|不能证明|无法确认/i.test(error)) return '赛事名称或主办方尚待确认，暂未接入公告。';
 if (item.status === '待核验' || /入口|栏目|未核验/i.test(error)) return '尚未确认可用的官方公告入口。';
 return '暂时无法获取官方公告，请稍后重试或打开官方页面。';
}

export function requestMessage(error) {
 const message = error?.message || String(error || '');
 return /HTTP|fetch|JSON|SyntaxError|TypeError|Traceback|参数|scope|college|read\/favorite/i.test(message)
  ? '暂时无法完成操作，请稍后重试。' : message;
}
