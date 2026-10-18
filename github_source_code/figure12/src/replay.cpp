#include "sketches.hpp"
#include "stable_alpha.hpp"
#include <fstream>
#include <iomanip>
#include <iostream>
using namespace wrapped;
int main(int argc,char**argv){try{
 if(argc!=7)throw std::runtime_error("pattern windows seed_start seed_count output budget");
 std::string pattern=argv[1];unsigned windows=std::stoul(argv[2]),start=std::stoul(argv[3]),seeds=std::stoul(argv[4]),budget=std::stoul(argv[6]);
 if(budget!=1000&&budget!=50000)throw std::runtime_error("budget");
 if(!seeds||!windows||windows>(pattern=="rise"?128u:512u)||(pattern!="drop"&&pattern!="rise"&&pattern!="cycle"))throw std::runtime_error("schedule");
 std::ofstream out(argv[5]);if(!out)throw std::runtime_error("output");
 out<<std::setprecision(17)<<"pattern,seed,window,truth,skmv_estimate,elastic_estimate,hll_estimate,tfm_estimate,hll_used,hll_peak,hll_capacity,hll_registers,tfm_registers,allocated_bits\n";
 const unsigned registers=budget==1000?4:256;
 const double alpha_m=stable_alpha(registers);
 for(unsigned s=start;s<start+seeds;++s){
  KMV32 a(budget,false,budget==1000?22:248),e(budget,true,budget==1000?21:247);
  HLL5 h(budget,registers);h.alpha_m=alpha_m;FM f(budget);
  if(h.capacity!=(budget==1000?48:1964)||f.m!=(budget==1000?3:173)||h.a.capacity()!=f.a.capacity())throw std::runtime_error("layout");
  u64 seed=mix(20261017+s),salt=mix(seed+1),x=0;
  for(unsigned w=0;w<windows;++w){
   bool high=pattern=="drop"?w<20:pattern=="rise"?w>=4:(w/64)%2==0;
   unsigned per_slot=high?10000:625;
   for(unsigned slot=0;slot<W;++slot){unsigned t=w*W+slot,tm=t%PERIOD;
    if(t%MAINTENANCE==0){a.maintenance(tm);e.maintenance(tm);h.maintenance(tm);f.maintenance(tm);}
    for(unsigned j=0;j<per_slot;++j,++x){u64 bh=mix(x^seed),rh=mix(x^salt);a.update(bh,rh,tm);e.update(bh,rh,tm);h.update(bh,rh,tm);f.update(bh,rh,tm);}
   }
   unsigned tm=((w+1)*W-1)%PERIOD;double av=a.query(tm),ev=e.query(tm),hv=h.query(tm),fv=f.query(tm);
   if(!std::isfinite(av)||!std::isfinite(ev)||av<0||ev<0||!std::isfinite(hv)||!std::isfinite(fv)||hv<0||fv<0)throw std::runtime_error("invalid estimate");
   out<<pattern<<','<<s<<','<<w+1<<','<<per_slot*W<<','<<av<<','<<ev<<','<<hv<<','<<fv<<','<<h.used<<','<<h.peak<<','<<h.capacity<<','<<h.m<<','<<f.m<<','<<h.a.capacity()<<'\n';
  }
  out.flush();std::cerr<<budget<<' '<<pattern<<" seed "<<s<<" PASS peak="<<h.peak<<'/'<<h.capacity<<" items="<<x<<'\n';
 }
}catch(const std::exception&e){std::cerr<<"ERROR "<<e.what()<<'\n';return 1;}}
