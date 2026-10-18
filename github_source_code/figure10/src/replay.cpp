#include "sketches.hpp"
#include "stable_alpha.hpp"
#include <fstream>
#include <iomanip>
#include <iostream>
using namespace wrapped;
std::vector<u64> grid(){std::vector<u64> v;for(int j=0;j<=80;++j)v.push_back(std::llround(std::pow(10.,3+j/20.)));return v;}
void execute(unsigned budget,unsigned m,unsigned ks,unsigned ke,unsigned trials,unsigned offset,int index,const std::string&path){
 std::ofstream out(path);if(!out)throw std::runtime_error("output open");
 out<<"algorithm,budget_bits,allocated_bits,m,k,cardinality,trial,query,time,wrapped_time,estimate,saturated,hll_peak,hll_capacity\n"<<std::setprecision(17);
 double alpha_m=stable_alpha(m);unsigned idx=0;
 for(u64 n:grid()){if(index>=0&&idx++!=unsigned(index))continue;
  for(unsigned trial=offset;trial<offset+trials;++trial){u64 seed=mix(20261013+trial);
   KMV32 a(budget,false,ks),e(budget,true,ke);FM f(budget);VATE v(budget);HLL5 h(budget,m);h.alpha_m=alpha_m;
   for(unsigned t=0;t<3*W;++t){unsigned tm=t%PERIOD;v.tick(t%200);
    if(t%MAINTENANCE==0){a.maintenance(tm);e.maintenance(tm);f.maintenance(tm);h.maintenance(tm);}
    unsigned epoch=t/W,slot=t%W;u64 lo=(u64(slot)*n+W-1)/W,hi=(u64(slot+1)*n+W-1)/W;
    for(u64 j=lo;j<hi;++j){u64 x=epoch*n+j,bh=mix(x^seed),rank=mix(x^mix(seed+1));
     a.update(bh,rank,tm);e.update(bh,rank,tm);f.update(bh,rank,tm);h.update(bh,rank,tm);v.update(bh,t%200);}
    if(t>=99&&(t-99)%25==0){
     auto emit=[&](const char* name,unsigned registers,unsigned k,double est,bool sat=false){out<<name<<','<<budget<<','<<a.a.capacity()<<','<<registers<<','<<k<<','<<n<<','<<trial<<','<<(t-99)/25<<','<<t<<','<<tm<<','<<est<<','<<sat<<','<<h.peak<<','<<h.capacity<<'\n';};
     bool sat=false;double ve=v.query(t%200,&sat);
     emit("Sliding HLL",h.m,0,h.query(tm));emit("Sliding KMV",a.m,a.k,a.query(tm));emit("Elastic S-KMV",e.m,e.k,e.query(tm));emit("VATE-LC",v.m,0,ve,sat);emit("T-FM",f.m,0,f.query(tm));
    }
   }
  }
  out.flush();std::cerr<<"budget="<<budget<<" n="<<n<<" trials="<<offset<<".."<<offset+trials-1<<" done\n";
 }
}
int main(int argc,char**argv){try{
 if(argc!=9)throw std::runtime_error("memory_bits hll_registers skmv_k elastic_k trials trial_offset cardinality_index_or_minus1 output");
 unsigned trials=std::stoul(argv[5]);int index=std::stoi(argv[7]);
 if(!trials||index < -1||index>80)throw std::runtime_error("invalid trials or cardinality index");
 execute(std::stoul(argv[1]),std::stoul(argv[2]),std::stoul(argv[3]),std::stoul(argv[4]),trials,std::stoul(argv[6]),index,argv[8]);
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
