#pragma once
#include "common.hpp"
#include <stdexcept>
#include <numeric>

namespace wrapped {
constexpr unsigned W=100, PERIOD=256, TB=8, MAINTENANCE=50;
inline unsigned age(unsigned now,unsigned then){return (now-then)&255;}
inline unsigned width(unsigned n){unsigned b=0;do{++b;n>>=1;}while(n);return b;}
// Every mutable sketch field lives in this fixed-capacity, word-rounded buffer.
// Configuration, hash seeds, and the common time source are external/read-only.
struct Bits {
 std::vector<u64> words;
 explicit Bits(size_t budget):words(budget/64,0){}
 size_t capacity()const{return words.size()*64;}
 static u64 mask(unsigned b){return b==64?~u64(0):(u64(1)<<b)-1;}
 u64 get(size_t pos,unsigned b)const{
  size_t w=pos>>6;unsigned o=pos&63;u64 v=words[w]>>o;
  if(o+b>64)v|=words[w+1]<<(64-o);
  return v&mask(b);
 }
 void set(size_t pos,unsigned b,u64 v){
  size_t w=pos>>6;unsigned o=pos&63;v&=mask(b);u64 m=mask(b);
  words[w]=(words[w]&~(m<<o))|(v<<o);
  if(o+b>64){unsigned r=o+b-64;words[w+1]=(words[w+1]&~mask(r))|(v>>(64-o));}
 }
};
template<unsigned HB> struct PackedKMV {
 static_assert(HB==32||HB==64,"supported hash widths");
 Bits a; unsigned k,m,qbits,stride;bool elastic;
 // Per bucket: theta[HB], last[8], occupancy[qbits], bounded[1],
 // k*(hash[HB],timestamp[8]), then optional candidate[HB],tau[8],g[8],
 // present[1],expired[1],mature[1].
 PackedKMV(size_t budget,bool e,unsigned kk=8):a(budget),k(kk),qbits(width(kk)),elastic(e){
  stride=HB+TB+qbits+1+k*(HB+TB)+(e?HB+2*TB+3:0);m=a.capacity()/stride;
  if(!m)throw std::runtime_error("KMV does not fit");
  for(unsigned i=0;i<m;++i)a.set(i*stride,HB,Bits::mask(HB));
 }
 size_t base(unsigned i)const{return size_t(i)*stride;}
 size_t item(unsigned i,unsigned j)const{return base(i)+HB+TB+qbits+1+j*(HB+TB);}
 size_t cand(unsigned i)const{return item(i,k);}
 unsigned count(unsigned i)const{return a.get(base(i)+HB+TB,qbits);}
 void count(unsigned i,unsigned n){a.set(base(i)+HB+TB,qbits,n);}
 bool bounded(unsigned i)const{return a.get(base(i)+HB+TB+qbits,1);}
 void bounded(unsigned i,bool v){a.set(base(i)+HB+TB+qbits,1,v);}
 void candidate_age(unsigned i,unsigned t){
  if(!elastic)return;size_t c=cand(i);
  if(!a.get(c+HB+16,1))return;
  if(!a.get(c+HB+17,1)&&age(t,a.get(c+HB,8))>=W)a.set(c+HB+17,1,1);
  if(!a.get(c+HB+18,1)&&age(t,a.get(c+HB+8,8))>=W)a.set(c+HB+18,1,1);
 }
 // Promotion is the sole expansion operation. Preserve the occurrence time.
 void promote(unsigned i,unsigned t){
  if(!elastic)return;
  size_t c=cand(i);unsigned n=count(i);
  if(n>=k||!a.get(c+HB+16,1)||a.get(c+HB+17,1)||!a.get(c+HB+18,1))return;
  u64 h=a.get(c,HB);unsigned ts=a.get(c+HB,8);
  a.set(item(i,n),HB,h);a.set(item(i,n)+HB,8,ts);
  count(i,n+1);a.set(base(i),HB,h);bounded(i,true);
  a.set(c+HB+16,3,0);
 }
 void expire(unsigned i,unsigned t){
  size_t b=base(i);
  if(age(t,a.get(b+HB,8))>=W){
   count(i,0);a.set(b,HB,Bits::mask(HB));a.set(b+HB+TB+qbits,1,0);
   if(elastic)a.set(cand(i)+HB+16,3,0);
   return;
  }
  unsigned out=0,n=count(i);
  for(unsigned j=0;j<n;++j){size_t p=item(i,j);u64 h=a.get(p,HB);unsigned ts=a.get(p+HB,8);
   if(age(t,ts)<W){size_t z=item(i,out++);a.set(z,HB,h);a.set(z+HB,8,ts);}}
  count(i,out);candidate_age(i,t);promote(i,t);
 }
 void maintenance(unsigned t){for(unsigned i=0;i<m;++i)expire(i,t);}
 void discard(unsigned i,u64 h,unsigned ts,unsigned t){
  size_t c=cand(i);candidate_age(i,t);bool has=a.get(c+HB+16,1);
  u64 old=has?a.get(c,HB):0;
  if(!has||(h>old&&a.get(c+HB+17,1))){
   a.set(c,HB,h);a.set(c+HB,8,ts);a.set(c+HB+8,8,t);a.set(c+HB+16,3,1);
  }else if(h<=old){
   if(h<old||a.get(c+HB+17,1)||age(t,ts)<age(t,a.get(c+HB,8)))a.set(c+HB,8,ts);
   a.set(c,HB,h);a.set(c+HB+17,1,0); // incoming/evicted pairs are active
  }
 }
 void update(u64 bh,u64 h,unsigned t){
  if constexpr(HB==32)h>>=32; // Preserve order with the high half of the rank hash.
  unsigned i=bh%m;size_t b=base(i);
  if(a.get(b+HB,8)!=t){expire(i,t);a.set(b+HB,8,t);}
  candidate_age(i,t);promote(i,t);
  u64 theta=a.get(b,HB);unsigned n=count(i);
  // Reject before duplicate scanning: no retained hash exceeds theta.
  if(h>theta){
   if(elastic){discard(i,h,t,t);promote(i,t);}
   return;
  }
  unsigned top=0;u64 maximum=0;
  for(unsigned j=0;j<n;++j){u64 v=a.get(item(i,j),HB);
   if(v==h){a.set(item(i,j)+HB,8,t);return;}
   if(j==0||v>maximum){maximum=v;top=j;}}
  unsigned dest=n<k?n:top;
  if(n==k&&elastic)discard(i,maximum,a.get(item(i,top)+HB,8),t);
  a.set(item(i,dest),HB,h);a.set(item(i,dest)+HB,8,t);
  if(n<k)count(i,++n);
  if(n==k){u64 mx=0;for(unsigned j=0;j<n;++j)mx=std::max(mx,a.get(item(i,j),HB));a.set(b,HB,mx);bounded(i,true);}
 }
 bool certified(unsigned i)const{return elastic&&a.get(cand(i)+HB+16,1)&&!a.get(cand(i)+HB+17,1)&&a.get(cand(i)+HB+18,1);}
 double query(unsigned t){
  maintenance(t);double total=0;
  for(unsigned i=0;i<m;++i){bool use=certified(i),sampled=use||bounded(i);u64 theta=use?a.get(cand(i),HB):a.get(base(i),HB);unsigned s=0;
   for(unsigned j=0;j<count(i);++j)s+=!sampled||a.get(item(i,j),HB)<theta;
   // Midpoint embedding avoids zero ranks. Equal stored ranks in one bucket
   // are treated as one identifier; no collision correction is fitted.
   double cutoff;if constexpr(HB==32)cutoff=std::ldexp(double(theta)+.5,-32);else cutoff=unit(theta);
   total+=sampled?s/cutoff:s;
  }return total;
 }
};
using KMV=PackedKMV<64>;
using KMV32=PackedKMV<32>;
struct FM {
 Bits a;unsigned m;static constexpr unsigned B=9,POSITIONS=32;
 explicit FM(size_t budget):a(budget),m(a.capacity()/(POSITIONS*B)){if(!m)throw std::runtime_error("FM does not fit");}
 bool active(unsigned p,unsigned t)const{u64 v=a.get(p*B,B);return (v&256)&&age(t,v&255)<W;}
 void maintenance(unsigned t){for(unsigned p=0;p<m*POSITIONS;++p)if(!active(p,t))a.set(p*B,B,0);}
 void update(u64 bh,u64 h,unsigned t){unsigned r=h?__builtin_clzll(h):64;if(r<POSITIONS)a.set(((bh%m)*POSITIONS+r)*B,B,256|t);}
 double query(unsigned t){maintenance(t);unsigned sum=0;for(unsigned i=0;i<m;++i){unsigned r=0;while(r<POSITIONS&&active(i*POSITIONS+r,t))++r;sum+=r;}
  return m*std::exp2(double(sum)/m)/(.77351*(1.+.31/m));
 }
};
struct VATE {
 Bits a;unsigned m;
 explicit VATE(size_t budget):a(budget),m(a.capacity()/8){for(unsigned i=0;i<m;++i)a.set(i*8,8,200);}
 // Staggered asynchronous clocks have period 2W, invalid sentinel 2W.
 void tick(unsigned t200){unsigned phase=(W-t200%W)%W;
  for(unsigned j=phase;j<m;j+=W){unsigned v=a.get(j*8,8),now=(t200+j%W)%200;
   if(v!=200&&(now+200-v)%200>=W)a.set(j*8,8,200);}}
 void update(u64 bh,unsigned t200){unsigned j=bh%m;a.set(j*8,8,(t200+j%W)%200);}
 bool active(unsigned j,unsigned t200)const{unsigned v=a.get(j*8,8);return v!=200&&((t200+j%W)%200+200-v)%200<W;}
 double query(unsigned t200,bool* saturated=nullptr)const{unsigned z=0;for(unsigned j=0;j<m;++j)z+=!active(j,t200);
  if(saturated)*saturated=z==0;
  return z?-double(m)*std::log(double(z)/m):double(m)*std::log(double(m));}
};
inline double alpha(unsigned m){
 // Numerical integration of Flajolet et al. (2007), Equation (3), after
 // x=1/(1+u). Simpson quadrature; configuration-only, outside the stream.
 constexpr unsigned steps=32768;long double sum=0;
 for(unsigned j=1;j<=steps;++j){long double x=(long double)j/steps;
  long double f=std::pow(std::log1p(x)/std::log(2.L),(int)m)/(x*x);
  sum+=f*(j==steps?1:j%2?4:2);}
 return 1./(m*(double)(sum/(3*steps)));
}
template<unsigned RB> struct PackedHLL {
 static_assert(RB==5||RB==7,"supported rank widths");
 static constexpr unsigned MAX_RANK=(1u<<RB)-1, NODE_FIELDS=8+RB;
 Bits a;unsigned m,pbits,capacity,nodebits;size_t nodes;double alpha_m;
 unsigned used=0,peak=0; // audit counters, not consulted by sketch decisions
 PackedHLL(size_t budget,unsigned registers):a(budget),m(registers),alpha_m(alpha(m)){
  // Null is index 0. Heads and one free-list head, then fixed packed nodes.
  capacity=0;pbits=0;
  for(unsigned p=1;p<20;++p){unsigned cap=(a.capacity()-(m+1)*p)/(NODE_FIELDS+p);
   if(a.capacity()<(m+1)*p)continue;
   cap=std::min(cap,(1u<<p)-1);if(cap>capacity){capacity=cap;pbits=p;}}
  if(!capacity)throw std::runtime_error("HLL does not fit");
  nodebits=NODE_FIELDS+pbits;nodes=(m+1)*pbits;
  a.set(m*pbits,pbits,1);
  for(unsigned j=1;j<=capacity;++j)setnext(j,j==capacity?0:j+1);
 }
 size_t pos(unsigned n)const{return nodes+size_t(n-1)*nodebits;}
 unsigned next(unsigned n)const{return a.get(pos(n)+NODE_FIELDS,pbits);}
 void setnext(unsigned n,unsigned v){a.set(pos(n)+NODE_FIELDS,pbits,v);}
 void release(unsigned n){setnext(n,a.get(m*pbits,pbits));a.set(m*pbits,pbits,n);--used;}
 void expire(unsigned i,unsigned t){unsigned n=a.get(i*pbits,pbits),prev=0;
  while(n){unsigned nx=next(n);if(age(t,a.get(pos(n),8))>=W){
    if(prev)setnext(prev,0);else a.set(i*pbits,pbits,0);
    while(n){nx=next(n);release(n);n=nx;}return;
   }prev=n;n=nx;}}
 void maintenance(unsigned t){for(unsigned i=0;i<m;++i)expire(i,t);}
 void update(u64 bh,u64 h,unsigned t){unsigned i=bh%m,rank=std::min(MAX_RANK,unsigned(h?__builtin_clzll(h)+1:65)),n=a.get(i*pbits,pbits);
  // Same-slot observations expire together: only their maximum can ever
  // determine a register. Coalesce before allocating another history node.
  if(n&&a.get(pos(n),8)==t&&a.get(pos(n)+8,RB)>=rank)return;
  while(n&&a.get(pos(n)+8,RB)<=rank){unsigned nx=next(n);release(n);n=nx;}
  unsigned free=a.get(m*pbits,pbits);
  if(!free)throw std::runtime_error("HLL pool exhausted: m="+std::to_string(m));
  a.set(m*pbits,pbits,next(free));a.set(pos(free),8,t);a.set(pos(free)+8,RB,rank);setnext(free,n);a.set(i*pbits,pbits,free);
  peak=std::max(peak,++used);
 }
 unsigned value(unsigned i)const{unsigned n=a.get(i*pbits,pbits),r=0;while(n){r=a.get(pos(n)+8,RB);n=next(n);}return r;}
 double query(unsigned t){maintenance(t);unsigned z=0;double sum=0;
  for(unsigned i=0;i<m;++i){unsigned r=value(i);z+=r==0;sum+=std::ldexp(1.,-int(r));}
  double e=alpha_m*m*m/sum;
  return e<=2.5*m&&z?-double(m)*std::log(double(z)/m):e;
 }
};
using HLL=PackedHLL<7>;
using HLL5=PackedHLL<5>;
}
