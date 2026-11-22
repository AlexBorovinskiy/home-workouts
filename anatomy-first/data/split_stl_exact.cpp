// Deterministic STL component cutter. Preserves all original facet vertices.
// Works by exact float-bit shared vertex IDs, not spatial or anatomical guesses.
// Build: g++ -std=c++17 -O2 split_stl_exact.cpp -o split_stl_exact
// Run: ./split_stl_exact /tmp/input.stl /tmp/components
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>
using namespace std;
using Key=array<uint32_t,3>;
struct Hash {
 size_t operator()(const Key& k) const noexcept {
  uint64_t h=1469598103934665603ULL;
  for(uint32_t x:k){h^=x;h*=1099511628211ULL;}
  return size_t(h);
 }
};
struct DSU {
 vector<uint32_t> parent;
 vector<uint8_t> rank;
 uint32_t add(){uint32_t n=parent.size();parent.push_back(n);rank.push_back(0);return n;}
 uint32_t find(uint32_t x){uint32_t root=x;while(parent[root]!=root)root=parent[root];while(parent[x]!=x){uint32_t y=parent[x];parent[x]=root;x=y;}return root;}
 void join(uint32_t a,uint32_t b){
  a=find(a);b=find(b);if(a==b)return;
  if(rank[a]<rank[b])swap(a,b);
  parent[b]=a;if(rank[a]==rank[b])rank[a]++;
 }
};
template<class T>T readNative(const char*p){T v;memcpy(&v,p,sizeof(T));return v;}
int main(int argc,char**argv){
 try{
  if(argc!=3)throw runtime_error("usage: split_stl_exact SOURCE.stl OUT_DIR");
  ifstream file(argv[1],ios::binary|ios::ate);
  if(!file)throw runtime_error("Could not open input");
  auto len=file.tellg();file.seekg(0);
  if(len<84)throw runtime_error("Invalid STL length");
  vector<char> bytes(static_cast<size_t>(len));
  if(!file.read(bytes.data(),len))throw runtime_error("Could not read input");
  uint32_t facets=readNative<uint32_t>(bytes.data()+80);
  if(bytes.size()!=84ULL+50ULL*facets)throw runtime_error("Wrong binary STL facet count");
  unordered_map<Key,uint32_t,Hash> lookup;lookup.reserve(size_t(facets)*2);
  DSU uf;uf.parent.reserve(facets*2);uf.rank.reserve(facets*2);
  vector<uint32_t> seed;seed.reserve(facets);
  for(uint32_t i=0;i<facets;i++){
   const char*p=bytes.data()+84ULL+50ULL*i;
   uint32_t ids[3];
   for(int v=0;v<3;v++){
    Key key;memcpy(key.data(),p+12+12*v,12);
    auto it=lookup.find(key);
    if(it==lookup.end()){uint32_t idx=uf.add();lookup.emplace(key,idx);ids[v]=idx;}
    else ids[v]=it->second;
   }
   uf.join(ids[0],ids[1]);uf.join(ids[0],ids[2]);seed.push_back(ids[0]);
  }
  unordered_map<uint32_t,vector<uint32_t>> groups;groups.reserve(60);
  for(uint32_t i=0;i<facets;i++)groups[uf.find(seed[i])].push_back(i);
  vector<const vector<uint32_t>*> sorted;sorted.reserve(groups.size());
  for(auto& item:groups)sorted.push_back(&item.second);
  sort(sorted.begin(),sorted.end(),[](auto*a,auto*b){return a->size()>b->size();});
  filesystem::create_directories(argv[2]);
  ofstream report(filesystem::path(argv[2])/"components.json");
  report<<"{\n \"source_triangles\": "<<facets<<",\n \"unique_vertex_coordinates\": "<<lookup.size()
        <<",\n \"connected_components\": "<<groups.size()<<",\n \"segments\": [\n";
  int exported=0;
  for(size_t i=0;i<sorted.size();i++){
   const auto& src=*sorted[i];
   if(i)report<<",\n";
   report<<"  {\"rank\": "<<i+1<<", \"triangles\": "<<src.size();
   if(src.size()>=100){
    exported++;
    auto filename="segment_"+(exported<10?string("0"):string(""))+to_string(exported)+".stl";
    ofstream out(filesystem::path(argv[2])/filename,ios::binary);
    array<char,80> header{};string marker="Unmodified MRI-derived hand STL facet subset";
    copy(marker.begin(),marker.end(),header.begin());
    out.write(header.data(),header.size());
    uint32_t count=src.size();out.write(reinterpret_cast<const char*>(&count),4);
    for(uint32_t id:src)out.write(bytes.data()+84ULL+50ULL*id,50);
    if(!out.good())throw runtime_error("Cannot save segment");
    report<<", \"file\": \""<<filename<<"\"";
   }
   report<<"}";
  }
  report<<"\n ],\n \"substantial_segments\": "<<exported<<"\n}\n";
  cout<<"INPUT_TRIANGLES "<<facets<<"\nUNIQUE_VERTICES "<<lookup.size()
      <<"\nCONNECTED_COMPONENTS "<<groups.size()<<"\nSUBSTANTIAL_SEGMENTS "<<exported<<"\n";
  for(size_t i=0;i<sorted.size()&&i<45;i++)cout<<"COMPONENT "<<i+1<<" faces "<<sorted[i]->size()<<"\n";
  return 0;
 }catch(const exception&e){cerr<<"ERROR: "<<e.what()<<"\n";return 1;}
}
