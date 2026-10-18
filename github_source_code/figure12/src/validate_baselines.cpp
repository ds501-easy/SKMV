#include "sketches.hpp"
#include "stable_alpha.hpp"
#include <iostream>
#include <array>
using namespace wrapped;
void need(bool ok,const char*why){if(!ok)throw std::runtime_error(why);}
int main(){try{
 u64 checks=0;
 for(unsigned budget:{1000,50000}){
  HLL5 h(budget,budget==1000?4:256);h.alpha_m=stable_alpha(h.m);FM f(budget);
  std::vector<std::array<int,32>> hl(h.m),fl(f.m);
  for(auto &x:hl)x.fill(-100000);for(auto &x:fl)x.fill(-100000);
  u64 x=0;
  for(unsigned t=0;t<1800;++t){unsigned tm=t%PERIOD;
   if(t%MAINTENANCE==0){h.maintenance(tm);f.maintenance(tm);}
   unsigned n=t%600<200?1500:t%600<350?50:0;
   for(unsigned j=0;j<n;++j,++x){u64 bh=mix(x^1234),rank=mix(x^5678);
    if(j==0)rank=0;if(j==1)rank=~u64(0);if(j==2)rank=u64(1)<<32;
    h.update(bh,rank,tm);f.update(bh,rank,tm);
    unsigned leading=rank?__builtin_clzll(rank):64;
    hl[bh%h.m][std::min(31u,leading+1)]=t;
    if(leading<32)fl[bh%f.m][leading]=t;
   }
   if(t%7&&t%100!=99)continue;
   double hv=h.query(tm),fv=f.query(tm),sum=0;unsigned zeros=0,total_r=0;
   for(unsigned i=0;i<h.m;++i){unsigned r=0;
    for(unsigned rank=1;rank<32;++rank)if(int(t)-hl[i][rank]<100)r=rank;
    need(h.value(i)==r,"HLL register differs from unwrapped oracle");sum+=std::ldexp(1.,-int(r));zeros+=r==0;++checks;
   }
   for(unsigned i=0;i<f.m;++i){unsigned r=0;
    while(r<32&&int(t)-fl[i][r]<100)++r;total_r+=r;
    for(unsigned rank=0;rank<32;++rank){need(f.active(i*32+rank,tm)==(int(t)-fl[i][rank]<100),"FM bit differs from unwrapped oracle");++checks;}
   }
   double he=h.alpha_m*h.m*h.m/sum;if(he<=2.5*h.m&&zeros)he=-double(h.m)*std::log(double(zeros)/h.m);
   double fe=f.m*std::exp2(double(total_r)/f.m)/(.77351*(1.+.31/f.m));
   need(std::abs(hv-he)<1e-12*std::max(1.,he),"HLL query oracle");need(std::abs(fv-fe)<1e-12*std::max(1.,fe),"FM query oracle");checks+=2;
  }
  std::cout<<"budget="<<budget<<" HLL peak="<<h.peak<<'/'<<h.capacity<<" FM registers="<<f.m<<'\n';
 }
 std::cout<<"PASS "<<checks<<" unwrapped oracle checks; multiple clock wraps, rate changes, idle periods, zero/max ranks\n";
}catch(const std::exception&e){std::cerr<<"FAIL "<<e.what()<<'\n';return 1;}}
