const fs=require('fs'); const src=fs.readFileSync(process.argv[2],'utf8');
const i=src.indexOf('function pxParse'), j=src.indexOf('function pxFields');
eval(src.slice(i,j));
const cases=[[{type:"http",host:"185.12.33.4",port:"8000",user:"bob",pass:"p:ss"},"http://bob:p%3Ass@185.12.33.4:8000"],
 [{type:"socks5",host:"1.2.3.4",port:"1080",user:"",pass:""},"socks5://1.2.3.4:1080"],
 [{type:"http",host:"1.2.3.4:8000:bob:pw",port:"",user:"",pass:""},"http://bob:pw@1.2.3.4:8000"],
 [{type:"http",host:"socks5://bob:pw@1.2.3.4:1080",port:"",user:"",pass:""},"socks5://bob:pw@1.2.3.4:1080"],
 [{type:"http",host:"",port:"1",user:"",pass:""},""]];
let ok=true; for (const [o,want] of cases){ const got=pxCompose(o); if(got!==want){ok=false; console.log("FAIL",JSON.stringify(o),got,want);} }
const p=pxParse("http://bob:p%3Ass@185.12.33.4:8000"); if(p.user!=="bob"||p.pass!=="p:ss"||p.host!=="185.12.33.4"||p.port!=="8000"){ok=false;console.log("FAIL parse",p);}
console.log(ok?"OK":"BAD");
