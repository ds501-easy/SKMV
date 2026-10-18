#pragma once
double stable_alpha(unsigned m){long double sum=0;const int steps=8192;const long double end=64;
 for(int j=0;j<=steps;++j){long double s=end*j/steps,x=std::exp(-s/m);
  long double f=std::exp(m*std::log(std::log1p(x)/std::log(2.L))+s/m);
  sum+=f*(j==0||j==steps?1:j%2?4:2);}
 return 1./double(sum*end/(3*steps));}
