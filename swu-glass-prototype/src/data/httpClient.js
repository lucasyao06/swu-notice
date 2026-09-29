export class ApiError extends Error {
 constructor(message,status=0){super(message);this.name='ApiError';this.status=status}
}
export function createHttpClient({baseUrl='/api',fetchImpl=globalThis.fetch,timeoutMs=15000}={}){
 return async function request(path,{method='GET',body,signal}={}){
  const controller=new AbortController();
  const abort=()=>controller.abort(signal?.reason);
  signal?.addEventListener('abort',abort,{once:true});if(signal?.aborted)abort();
  const timer=setTimeout(()=>controller.abort(new Error('请求超时')),timeoutMs);
  try{
   const response=await fetchImpl(`${baseUrl.replace(/\/$/,'')}${path}`,{method,signal:controller.signal,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});
   const data=await response.json().catch(()=>{throw new ApiError('接口未返回有效 JSON，请检查 API 代理配置',response.status)});
   if(!response.ok)throw new ApiError(data.error||`请求失败（${response.status}）`,response.status);
   return data;
  }catch(error){
   if(signal?.aborted)throw error;
   if(error instanceof ApiError)throw error;
   throw new ApiError(controller.signal.aborted?'后端响应超时，请重试':'无法连接通知后端，请检查服务是否运行');
  }finally{clearTimeout(timer);signal?.removeEventListener('abort',abort)}
 }
}
