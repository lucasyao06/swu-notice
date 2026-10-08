export function dockInfluence(distance,radius=120){
 const proximity=Math.max(0,1-Math.abs(distance)/radius);
 return proximity*proximity*(3-2*proximity);
}
