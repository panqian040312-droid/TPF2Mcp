window.renderRailNetwork = function renderRailNetwork() {
  const p = window.RAIL_NETWORK_DATA;
  const templates = window.RailMapTemplates;
  const svg = document.querySelector('#board');
  const tooltip = document.querySelector('#track-tooltip');
  const boardWrap = document.querySelector('#board-wrap');
  $('#local-view').removeClass('selected').off('.stationPreview').on('click.stationPreview', event => {
    event.preventDefault();
    if (!selectedStation) {
      window.showRailMapNotice('请选择对应车站');
      return;
    }
    const target = new URL(window.location.href);
    target.search = '';
    target.searchParams.set('view', 'local');
    target.searchParams.set('station', selectedStation.entity_id);
    window.location.assign(target.href);
  });
  $('#network-view').addClass('selected').off('.stationPreview').on('click.stationPreview', event => event.preventDefault());
  if (!p || p.source_status !== 'ENGINE_OBSERVED') {
    document.querySelector('#station-name').textContent = '全路网';
    document.querySelector('#snapshot').textContent = '等待一次性铁路拓扑导出';
    document.querySelector('.mode').textContent = 'NETWORK CONTROL · PENDING';
    const pending = templates.instantiate('pending-sidebar-template');
    templates.slot(pending, 'message').appendChild(templates.message('PENDING', '尚未生成 rail-network-data.js', true));
    document.querySelector('#sidebar').replaceChildren(pending);
    const NS = 'http://www.w3.org/2000/svg';
    const message = document.createElementNS(NS, 'text');
    Object.entries({x:600,y:360,fill:'#ffbd52','font-size':16,'text-anchor':'middle','font-family':'Microsoft YaHei'}).forEach(([k,v]) => message.setAttribute(k,v));
    message.textContent = '全路网数据尚未导出'; svg.appendChild(message);
    return;
  }

  const NS = 'http://www.w3.org/2000/svg';
  const S = (tag, attrs = {}, text = '', parent = svg) => {
    const node = document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
    if (text) node.textContent = text;
    parent.appendChild(node);
    return node;
  };
  // 地图朝向：把世界坐标整体旋转 mapHeading 度（视觉逆时针），用于对齐游戏内视角。
  // 0° = 原始朝向（世界 +x 向右）；90° = 逆时针转 90°（原来在屏幕左侧的轨道会转到屏幕下方）。
  const headingParam = new URLSearchParams(location.search).get('heading');
  const headingStored = (() => { try { return localStorage.getItem('railMapHeading'); } catch (error) { return null; } })();
  let mapHeading = Number(headingParam != null ? headingParam : (headingStored != null ? headingStored : 90));
  if (!Number.isFinite(mapHeading)) mapHeading = 90;
  let baseScale = 1, originX = 0, originY = 0;
  let rot = (x, y) => ({ x: x, y: y });
  let rotInv = (x, y) => ({ x: x, y: y });
  let P = point => ({ x: 0, y: 0 });
  let T = value => ({ x: 0, y: 0 });
  const rebuildProjection = () => {
    const hRad = mapHeading * Math.PI / 180, hCos = Math.cos(hRad), hSin = Math.sin(hRad);
    rot = (x, y) => ({ x: x * hCos - y * hSin, y: x * hSin + y * hCos });
    rotInv = (x, y) => ({ x: x * hCos + y * hSin, y: -x * hSin + y * hCos });
    const b = p.bounds;
    const corners = [[b.min.x, b.min.y], [b.max.x, b.min.y], [b.min.x, b.max.y], [b.max.x, b.max.y]].map(([x, y]) => rot(x, y));
    const minX = Math.min(...corners.map(v => v.x)), maxX = Math.max(...corners.map(v => v.x));
    const minY = Math.min(...corners.map(v => v.y)), maxY = Math.max(...corners.map(v => v.y));
    const width = Math.max(1, maxX - minX), height = Math.max(1, maxY - minY);
    baseScale = Math.min(1080 / width, 620 / height);
    originX = 600 - (minX + maxX) * baseScale / 2;
    originY = 360 + (minY + maxY) * baseScale / 2;
    P = point => { const r = rot(point.x, point.y); return { x: originX + r.x * baseScale, y: originY - r.y * baseScale }; };
    T = value => { const r = rot(value.x, value.y); return { x: r.x * baseScale, y: -r.y * baseScale }; };
  };
  rebuildProjection();
  const edgePath = (edge,nodeById) => {
    const a=nodeById.get(edge.node0), b=nodeById.get(edge.node1), pa=P(a), pb=P(b);
    const fallback={x:b.x-a.x,y:b.y-a.y};
    const ta=T(edge.tangent0||fallback), tb=T(edge.tangent1||fallback);
    return `M${pa.x.toFixed(2)},${pa.y.toFixed(2)}C${(pa.x+ta.x/3).toFixed(2)},${(pa.y+ta.y/3).toFixed(2)} ${(pb.x-tb.x/3).toFixed(2)},${(pb.y-tb.y/3).toFixed(2)} ${pb.x.toFixed(2)},${pb.y.toFixed(2)}`;
  };
  const edgeCurve=(edge,nodeById)=>{const a=nodeById.get(edge.node0),b=nodeById.get(edge.node1),pa=P(a),pb=P(b),fallback={x:b.x-a.x,y:b.y-a.y},ta=T(edge.tangent0||fallback),tb=T(edge.tangent1||fallback);return{a:pa,c1:{x:pa.x+ta.x/3,y:pa.y+ta.y/3},c2:{x:pb.x-tb.x/3,y:pb.y-tb.y/3},b:pb};};
  const drawPixiEdge=(graphics,edge,nodeById)=>{const c=edgeCurve(edge,nodeById);graphics.moveTo(c.a.x,c.a.y).bezierCurveTo(c.c1.x,c.c1.y,c.c2.x,c.c2.y,c.b.x,c.b.y);};
  const mapLayer=S('g',{id:'network-map-layer'});
  const platformLayer=S('g',{id:'network-platform-layer'},'',mapLayer);
  const detailLayer=S('g',{id:'network-detail-layer'},'',mapLayer);
  const bridgeLayer=S('g',{id:'network-bridge-layer'},'',mapLayer);
  let pixiApp=null;
  // ⚠️ `autoStart:false` 是**必须的**，两个原因：
  //   ① 性能：默认开启时 Pixi 自带 ticker，**即使什么都不动也每帧重绘整块 canvas**。
  //      本机 GPU/CPU 基本都让给游戏了，前端不能偷偷空转。关掉后，只有我们显式 render 才画。
  //   ② 正确性（用户 2026-09-30 报的"拖动时铁路线迟滞然后复位"）：
  //      开着 autoStart 时 Pixi 有自己的 rAF，而 SVG 的更新在 schedulePanRender 的另一个 rAF 里，
  //      两个渲染器不同帧 —— Pixi 层（铁路网）永远慢一帧，松手才追上。
  //      关掉它、改成在 updateViewport() 末尾**同步** render，两层就同帧了。
  try{if(window.PIXI)pixiApp=new PIXI.Application({resizeTo:boardWrap,backgroundAlpha:0,antialias:true,autoDensity:true,resolution:Math.min(window.devicePixelRatio||1,2),powerPreference:'high-performance',autoStart:false});}catch(error){console.error('PixiJS rail renderer unavailable; using SVG fallback',error);}
  // Pixi 内容变了（分块增删）才需要重画 —— 用 rAF 去重，避免一次加载多块时重复 render。
  let pixiRenderFrame=0;
  const schedulePixiRender=()=>{if(!pixiApp||pixiRenderFrame||document.hidden)return;pixiRenderFrame=requestAnimationFrame(()=>{pixiRenderFrame=0;if(pixiApp)pixiApp.render();});};
  const pixiWorld=pixiApp?new PIXI.Container():null;
  if(pixiApp){pixiApp.view.id='rail-webgl';pixiApp.stage.addChild(pixiWorld);boardWrap.insertBefore(pixiApp.view,svg);}

  const physicalOverviewPath=(p.physical_overview_segments||[]).map(segment=>segment.map((point,index)=>{const q=P({x:point[0],y:point[1]});return `${index?'L':'M'}${q.x.toFixed(2)},${q.y.toFixed(2)}`;}).join('')).join('');
  const physicalOverview=physicalOverviewPath?S('path',{d:physicalOverviewPath,fill:'none',stroke:'#83a9bd','stroke-width':1.15,opacity:1,'vector-effect':'non-scaling-stroke','pointer-events':'none','data-layer':'physical-overview'},'',mapLayer):null;

  const stationLayer=S('g',{id:'network-station-layer'});
  const depotLayer=S('g',{id:'network-depot-layer'});
  const liveLayer=S('g',{id:'network-live-layer'});
  // 船 / 飞机的实时层（与铁路分开）：它们**不挂在 BASE_EDGE_* 上**（实测 current_edge_id
  // 全为空），位置直接来自服务端从遥测里挑出来的包围盒中心，所以不走下面那套轨道吸附。
  // 挂 svg 根、用 screenPoint —— 和 liveLayer 一样是"屏幕坐标的标记层"。
  const otherVehicleLayer=S('g',{id:'network-other-vehicle-layer','pointer-events':'none'});
  // 线路高亮的站点标记层：单独挂 **svg 根**（屏幕坐标）—— 它们是"标记"，必须固定屏幕尺寸。
  // 挂在 mapLayer 里的话 zoom=1 时 r=5 世界单位只有 0.2 px，全图根本看不见。
  // ⚠️ 这一组必须定义在 updateViewport **被首次调用之前**：`setCollapsed()` 在脚本执行期
  //    就立刻调 updateViewport()，而这些是 const/let（暂时性死区），放后面会直接报错白屏。
  const lineStopLayer=S('g',{id:'network-line-stop-layer','pointer-events':'none'});
  let lineGapInfo={count:0,skipped:0};   // 本次高亮补了几段缺口（侧边栏要如实说明）
  let lineStopMarks=[];              // {circle,label,position} —— 平移缩放时重算屏幕坐标
  const updateLineStopMarks=()=>{
    lineStopMarks.forEach(mark=>{
      const q=screenPoint(mark.position);
      mark.group.setAttribute('transform',`translate(${q.x.toFixed(1)} ${q.y.toFixed(1)})`);
    });
  };
  const stationViews=[];
  const depotViews=[];
  const platformViews=[];
  const trainViews=new Map(),signalViews=new Map();
  // 船 / 飞机的视图。**分两张表**，否则同步时要靠 carrier 区分该删谁，容易误删。
  const airViews=new Map(),waterViews=new Map();
  // 用户 2026-09-29 定：飞机跟列车同频（随 500 ms 的 /api/live 一起走），船 90 秒才刷新一次。
  const WATER_REFRESH_MS=90000;
  const OTHER_MARK_RADIUS=4;      // 屏幕像素半径，直径 8 px，与车辆图层一致
  // 「交通工具 · 种类」那几个框是**唯一**的显示控制点（勾谁显示谁，全不勾 = 都不显示）。
  // 这里用一个"可赋值函数"而不是直接引用 FILTER —— FILTER 定义在这后面，
  // 直接引用会踩 const 暂时性死区；applyFilters 负责把它换成真正的判定函数。
  let carrierVisibleFn=()=>true;
  let waterCommittedAt=0;         // 0 = 还没画过，第一次立刻落位
  let signalsVisible=true;
  const lineById=new Map(p.lines.map(line=>[line.entity_id,line]));
  const stationById=new Map(p.stations.map(station=>[station.entity_id,station]));
  let liveState=null,operationsContext={lines:[]},aiAdvice={suggestions:[]},aiAdviceVisibleCount=10,aiAdviceGeneration=null,mcpWorkLog={entries:[]},allMcpWorkLog={entries:[]},workLogModal=null,workLogFilter='ALL',workLogSearch='',workLogRequestPending=false,workLogLoadError=null,workLogReturnFocus=null,selectedStation=null,selectedVehicleId=null,vehicleDetail=null,vehicleDetailPending=false,vehicleDetailLoadedAt=0,overviewKey=null;
  const operationLineById=new Map();
  let stationLogRows=[],stationLogRequestPending=false;
  let lastVehicleSampleAt=null;
  const stationsByPlatformEdge=new Map();
  p.stations.forEach(station=>(station.terminals||[]).forEach(terminal=>(terminal.platform_edge_ids||[]).forEach(edgeId=>{const values=stationsByPlatformEdge.get(edgeId)||[];if(!values.some(item=>item.entity_id===station.entity_id))values.push(station);stationsByPlatformEdge.set(edgeId,values);}))); 
  const normalizedStationName=station=>String(station.name||'').trim().toLocaleLowerCase('zh-CN');
  const sameLogicalYard=(station,other)=>normalizedStationName(other)===normalizedStationName(station)&&Math.hypot(other.center.x-station.center.x,other.center.y-station.center.y)<=500;
  const relatedStations=station=>p.stations.filter(other=>sameLogicalYard(station,other));
  const logicalStations=p.stations.filter((station,index)=>!p.stations.slice(0,index).some(other=>sameLogicalYard(station,other)));
  const terminalSelectorKey=(stationId,stationIndex,terminalId)=>`${stationId}:${stationIndex}:${terminalId}`;
  const lineServesPassengerTerminal=(line,station)=>{
    const selectors=new Set(relatedStations(station).flatMap(item=>(item.terminals||[]).filter(terminal=>!terminal.cargo).map(terminal=>terminalSelectorKey(item.entity_id,terminal.station_index,terminal.terminal_index))));
    return (line.stops||[]).some(stop=>{
      if(selectors.has(terminalSelectorKey(stop.station_id,stop.station_index,stop.terminal_id)))return true;
      return (stop.alternative_terminals||[]).some(terminal=>selectors.has(terminalSelectorKey(stop.station_id,terminal.station_index,terminal.terminal_id)));
    });
  };
  const stationPassengerServiceClass=station=>{
    let high=0,conventional=0,unknown=0;
    (operationsContext.lines||[]).filter(line=>lineServesPassengerTerminal(line,station)).forEach(line=>{
      const vehicles=line.active_passenger_vehicles||{};
      high+=Number(vehicles.high_speed)||0;
      conventional+=Number(vehicles.conventional)||0;
      unknown+=Number(vehicles.unknown_speed)||0;
    });
    if(high&&conventional)return 'MIXED';
    if(unknown)return 'UNKNOWN';
    if(high)return 'HIGH_SPEED';
    if(conventional)return 'CONVENTIONAL';
    return 'UNKNOWN';
  };
  const stationYardLabel=station=>{
    const terminals=relatedStations(station).flatMap(item=>item.terminals||[]),passenger=terminals.some(terminal=>!terminal.cargo),cargo=terminals.some(terminal=>terminal.cargo);
    if(!passenger)return cargo?'普速场(货)':'';
    const serviceClass=stationPassengerServiceClass(station);
    if(serviceClass==='CONVENTIONAL')return cargo?'普速场(客-货)':'普速场(客)';
    const passengerLabel=serviceClass==='HIGH_SPEED'?'高速场(客)':serviceClass==='MIXED'?'高普混合场(客)':'客运场(待确认)';
    return cargo?`${passengerLabel}/普速场(货)`:passengerLabel;
  };
  const stationBaseName=station=>{const name=String(station.name||`车站 ${station.entity_id}`);return name.endsWith('站')?name.slice(0,-1):name;};
  const stationPreview=station=>{const name=stationBaseName(station),yard=stationYardLabel(station);return yard?`${name}-${yard}`:name;};
  const physicalPlatforms=station=>station.platforms||(station.terminals||[]).map((terminal,index)=>({platform_index:index,platform_kind:'SIDE_OR_SINGLE_FACE',cargo:terminal.cargo,terminal_faces:[{station_index:terminal.station_index,terminal_index:terminal.terminal_index,node_id:terminal.node_id}],platform_centerline:terminal.platform_centerline||terminal.operating_track_centerline||[],platform_length_m:terminal.platform_length_m}));
  const depotDisplayName=depot=>{
    const fallback=`车辆段 ${depot.entity_id}`;
    const name=String(depot.name||fallback).trim();
    return ({'汉口所':'汉口动车所','武汉所':'武汉动车所'})[name]||name;
  };
  const sideOfPolyline=(points,point)=>{
    let bestDistance=Infinity,bestSide=0;
    for(let index=0;index+1<points.length;index+=1){
      const a=points[index],b=points[index+1],dx=b[0]-a[0],dy=b[1]-a[1],lengthSquared=dx*dx+dy*dy;
      if(lengthSquared<=1e-9)continue;
      const ratio=Math.max(0,Math.min(1,((point.x-a[0])*dx+(point.y-a[1])*dy)/lengthSquared));
      const nearest={x:a[0]+dx*ratio,y:a[1]+dy*ratio},distance=(point.x-nearest.x)**2+(point.y-nearest.y)**2;
      if(distance<bestDistance){bestDistance=distance;bestSide=dx*(point.y-nearest.y)-dy*(point.x-nearest.x);}
    }
    return bestSide;
  };
  const faceForPointer=(station,platform,event)=>{
    const faces=platform.terminal_faces||[];
    if(faces.length<2)return faces[0];
    const rect=boardWrap.getBoundingClientRect(),screenX=(event.clientX-rect.left)*1200/rect.width,screenY=(event.clientY-rect.top)*720/rect.height;
    const pointerSide=sideOfPolyline(platform.platform_centerline,worldPoint(screenX,screenY));
    const terminalByIndex=new Map((station.terminals||[]).map(terminal=>[terminal.terminal_index,terminal]));
    return faces.reduce((best,face)=>{
      const terminal=terminalByIndex.get(face.terminal_index),track=terminal?.operating_track_centerline||terminal?.platform_centerline||[];
      if(track.length<2)return best;
      const middle=track[Math.floor(track.length/2)],score=sideOfPolyline(platform.platform_centerline,{x:middle[0],y:middle[1]})*pointerSide;
      return !best||score>best.score?{face,score}:best;
    },null)?.face||faces[0];
  };
  const servedStationIds=new Set(p.lines.flatMap(line=>line.stops.map(stop=>stop.station_group_id)));
  p.stations.forEach(station=>{
    physicalPlatforms(station).forEach(platform=>{
      const platformLine=platform.platform_centerline||[],hitLine=platformLine;
      if(hitLine.length>=2){
        const widthUnits=platform.platform_width_units||(platform.platform_kind==='ISLAND'?2:1);
        const makePath=line=>line.map((point,index)=>{const q=P({x:point[0],y:point[1]});return `${index?'L':'M'}${q.x.toFixed(5)},${q.y.toFixed(5)}`;}).join('');
        const platformPath=platformLine.length>=2?makePath(platformLine):'';
        const hitPath=makePath(hitLine);
        const outline=platformPath?S('path',{d:platformPath,fill:'none',stroke:'#26343d','stroke-width':6*widthUnits+2,'vector-effect':'non-scaling-stroke','stroke-linecap':'round','stroke-linejoin':'round','pointer-events':'none'},'',platformLayer):null;
        const surface=platformPath?S('path',{d:platformPath,fill:'none',stroke:'#96a2a8','stroke-width':6*widthUnits,'vector-effect':'non-scaling-stroke','stroke-linecap':'round','stroke-linejoin':'round','pointer-events':'none'},'',platformLayer):null;
        const divider=platform.platform_kind==='ISLAND'?S('path',{d:platformPath,fill:'none',stroke:'#58656d','stroke-width':1,'stroke-dasharray':'4 3','vector-effect':'non-scaling-stroke','pointer-events':'none',display:'none'},'',platformLayer):null;
        const hit=S('path',{d:hitPath,fill:'none',stroke:'transparent','stroke-width':6*widthUnits+4,'vector-effect':'non-scaling-stroke','stroke-linecap':'round','pointer-events':'stroke',cursor:'pointer'},'',platformLayer);
        const show=event=>{if(divider)divider.style.display='block';const face=faceForPointer(station,platform,event),kind=platform.cargo?'货':'客';tooltip.textContent=`${Number(face?.terminal_index??platform.platform_index)+1}站台（${kind}）`;tooltip.style.display='block';};
        hit.addEventListener('pointerenter',show);hit.addEventListener('pointermove',event=>{show(event);moveTooltip(event);});hit.addEventListener('pointerleave',()=>{if(divider)divider.style.display='none';tooltip.style.display='none';});
        platformViews.push({outline,surface,divider,hit,station,platform,widthUnits});
      }
    });
  });
  const moveTooltip=event=>{const rect=boardWrap.getBoundingClientRect();tooltip.style.left=`${event.clientX-rect.left+12}px`;tooltip.style.top=`${event.clientY-rect.top+12}px`;};
  const scaleBarPixels=92;
  let zoom=1,panX=0,panY=0,dragging=false,dragPointerId=null,lastX=0,lastY=0,dragStartX=0,dragStartY=0,suppressClick=false;
  // 分块状态不再是单例：铁路与新增图层（公路/产业/车辆）各有一份，
  // 由下面的 createTileLayer 统一管理。
  let bridgeRenderFrame=null;
  const renderVisibleBridges=()=>{
    bridgeRenderFrame=null;
    bridgeLayer.replaceChildren();
    const crossings=[],fallbackEdges=[],fallbackNodes=new Map();
    const visibleEdgePaths=new Map(),visibleEdges=new Map(),visibleNodes=new Map(),visibleEdgeIdsByNode=new Map();
    railLayer.loaded.forEach(entry=>{
      entry.paths.forEach((path,edgeId)=>visibleEdgePaths.set(Number(edgeId),path));
      entry.tileNodes.forEach((position,nodeId)=>visibleNodes.set(Number(nodeId),position));
      entry.tile.edges.forEach(edge=>{
        visibleEdges.set(Number(edge.entity_id),edge);
        [edge.node0,edge.node1].forEach(nodeId=>{
          const key=Number(nodeId),values=visibleEdgeIdsByNode.get(key)||[];
          if(!values.includes(Number(edge.entity_id)))values.push(Number(edge.entity_id));
          visibleEdgeIdsByNode.set(key,values);
        });
      });
      if(Array.isArray(entry.tile.grade_separated_crossings))crossings.push(...entry.tile.grade_separated_crossings);
      else{
        entry.tile.edges.forEach(edge=>fallbackEdges.push(edge));
        entry.tileNodes.forEach((position,nodeId)=>fallbackNodes.set(nodeId,position));
      }
    });
    if(fallbackEdges.length)crossings.push(...window.RailBridgeCrossings.detect(fallbackEdges,fallbackNodes));
    window.RailBridgeCrossings.renderSvg(crossings,P,S,bridgeLayer,{
      trackStrokeWidth:1,
      upperPathForEdge:edgeId=>visibleEdgePaths.get(Number(edgeId)),
      upperEdgeIdsForBridge:(crossing,shape)=>window.RailBridgeCrossings.expandUpperEdgeIds(
        crossing,shape,visibleEdges,visibleNodes,visibleEdgeIdsByNode,
      ),
      upperPointsForEdge:edgeId=>{
        const edge=visibleEdges.get(Number(edgeId));
        return edge?window.RailBridgeCrossings.sampleEdge(edge,visibleNodes):null;
      },
    });
  };
  const scheduleBridgeRender=()=>{
    if(bridgeRenderFrame!==null)return;
    bridgeRenderFrame=requestAnimationFrame(renderVisibleBridges);
  };
  const pixiDomScale=()=>{const rect=boardWrap.getBoundingClientRect();return Math.min(rect.width/1200,rect.height/720);};
  const syncPixiViewport=()=>{if(!pixiWorld)return;const rect=boardWrap.getBoundingClientRect(),scale=pixiDomScale(),offsetX=(rect.width-1200*scale)/2,offsetY=(rect.height-720*scale)/2;pixiWorld.scale.set(scale*zoom);pixiWorld.position.set(offsetX+scale*(600+panX-600*zoom),offsetY+scale*(360+panY-360*zoom));};
  const makePixiTile=(tile,nodeById)=>{if(!pixiWorld)return null;const container=new PIXI.Container(),track=new PIXI.Graphics();track.lineStyle(1,0x83a9bd,1,.5,true);tile.edges.forEach(edge=>drawPixiEdge(track,edge,nodeById));container.addChild(track);pixiWorld.addChild(container);return{container};};
  window.RAIL_NETWORK_TILES={};
  const updateTileStatus=()=>{const value=document.querySelector('#loaded-tile-count');if(value)value.textContent=`${railLayer.loaded.size} / ${p.tiles.length}`;};
  const representedMeters=()=>scaleBarPixels/baseScale/zoom;
  // 🔴 这两个输出**只依赖 zoom 落在哪个档位**（要不要显示细节、有没有近到能看清站台宽度），
  //    平移时完全不变。原来每帧都往 185 个站台 × 6 个属性上重写一遍 ——
  //    约 1100 次/帧、6.6 万次/秒，是这份地图最大的每帧开销，而且**写进去的值与上一帧一模一样**。
  //    加档位缓存：没跨档就直接整段跳过。
  let detailState = null, closeState = null;
  const updateMapDetailVisibility=()=>{
    const meters = representedMeters();
    const detail = meters < p.detail_load_threshold_m;
    const closePlatforms = meters < 120;
    if (detail === detailState && closePlatforms === closeState) return;
    detailState = detail; closeState = closePlatforms;
    if(physicalOverview)physicalOverview.setAttribute('opacity',detail?0:1);
    platformViews.forEach(view=>{if(view.outline){view.outline.style.display=detail?'block':'none';view.outline.setAttribute('stroke-width',(closePlatforms?6:1.5)*view.widthUnits+2);}if(view.surface){view.surface.style.display=detail?'block':'none';view.surface.setAttribute('stroke-width',(closePlatforms?6:1.5)*view.widthUnits);}if(!detail&&view.divider)view.divider.style.display='none';view.hit.setAttribute('stroke-width',(closePlatforms?6:1.5)*view.widthUnits+4);view.hit.setAttribute('pointer-events',detail?'stroke':'none');});
  };
  const screenPoint=point=>{const q=P(point);return{x:600+(q.x-600)*zoom+panX,y:360+(q.y-360)*zoom+panY};};
  const worldPoint=(x,y)=>{
    const baseX=(x-panX-600)/zoom+600,baseY=(y-panY-360)/zoom+360;
    const r=rotInv((baseX-originX)/baseScale,(originY-baseY)/baseScale);
    return{x:r.x,y:r.y};
  };
  logicalStations.forEach(station=>{
    const group=S('g',{'data-station-id':station.entity_id,cursor:'pointer'},'',stationLayer);
    const dot=S('circle',{r:3.2,fill:'#08141e',stroke:'#83ecff','stroke-width':1.2},'',group);
    // 站名字号：用户 2026-09-30 反馈「太小了」—— 7.5 → 11（描边同步加粗，不然字会被压糊）
    const name=S('text',{x:6,y:-5,visibility:'hidden',fill:'#c8f3ff','font-size':11,'font-family':'Consolas, Microsoft YaHei','paint-order':'stroke','stroke':'#061019','stroke-width':3,'stroke-linejoin':'round'},station.name,group);
    const hit=S('circle',{r:10,fill:'transparent','pointer-events':'fill',cursor:'pointer'},'',group);
    const show=()=>{tooltip.textContent=stationPreview(station);tooltip.style.display='block';dot.setAttribute('fill','#56dcff');name.setAttribute('visibility','visible');};
    hit.addEventListener('pointerenter',show);hit.addEventListener('pointermove',event=>{show();moveTooltip(event);});hit.addEventListener('pointerleave',()=>{tooltip.style.display='none';dot.setAttribute('fill','#08141e');updateStations();});
    group.addEventListener('pointerdown',event=>{if(event.button===0)event.stopPropagation();});
    group.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();selectedVehicleId=null;vehicleDetail=null;selectedStation=station;stationLogRows=[];renderStationSidebar();loadStationLogs();updateStations();});
    // 双击车站 = 直接进入该站的局部视图（原来只是原地放大，看不出附近的枢纽/客流）。
    // 局部视图由 app.js 处理（URL 带 ?view=local&station=<id>），那边会显示站台、
    // 附近交通枢纽和本站客货。
    hit.addEventListener('dblclick',()=>{
      const target=new URL(location.href);
      target.search='';
      target.searchParams.set('view','local');
      target.searchParams.set('station',String(station.entity_id));
      location.assign(target.href);
    });
    stationViews.push({station,group,dot,name,hit,served:relatedStations(station).some(item=>servedStationIds.has(item.entity_id))});
  });
  (p.depots||[]).forEach(depot=>{
    const connector=S('line',{stroke:'#5cc7d8','stroke-width':1,'stroke-dasharray':'3 2',opacity:.8,'pointer-events':'none'},'',depotLayer);
    const group=S('g',{'data-depot-id':depot.entity_id,cursor:'help'},'',depotLayer);
    const marker=S('path',{d:'M-5,-4 L5,-4 L5,4 L-5,4 Z M-2,4 L-2,-1 L2,-1 L2,4',fill:'#102936',stroke:'#62e0ec','stroke-width':1.2,'fill-rule':'evenodd'},'',group);
    S('text',{x:0,y:-7,fill:'#9ef4fa','font-size':6.5,'font-family':'Consolas, Microsoft YaHei','text-anchor':'middle','paint-order':'stroke',stroke:'#061019','stroke-width':2},depotDisplayName(depot),group);
    const show=event=>{
      const parked=depot.parked_vehicle_count_source==='UNKNOWN'?'场内车辆 UNKNOWN':`场内 ${depot.parked_vehicle_count}`;
      tooltip.textContent=`${depotDisplayName(depot)} · 配属 ${depot.assigned_vehicle_count} · ${parked}`;
      tooltip.style.display='block';marker.setAttribute('fill','#1f6170');moveTooltip(event);
    };
    group.addEventListener('pointerenter',show);group.addEventListener('pointermove',show);group.addEventListener('pointerleave',()=>{tooltip.style.display='none';marker.setAttribute('fill','#102936');});
    depotViews.push({depot,group,connector});
  });

  const barY=682,barX=58;
  S('line',{x1:barX,y1:barY,x2:barX+scaleBarPixels,y2:barY,stroke:'#dce7ef','stroke-width':3});
  S('line',{x1:barX,y1:barY-5,x2:barX,y2:barY+5,stroke:'#dce7ef','stroke-width':2});
  S('line',{x1:barX+scaleBarPixels,y1:barY-5,x2:barX+scaleBarPixels,y2:barY+5,stroke:'#dce7ef','stroke-width':2});
  const scaleText=S('text',{x:barX+scaleBarPixels/2,y:barY-9,fill:'#dce7ef','font-size':10,'font-family':'Consolas','text-anchor':'middle'});
  const formatDistance=value=>value>=1000?`${(value/1000).toFixed(value>=10000?0:1)} km`:`${value.toFixed(value<10?1:0)} m`;
  // ===== 分块图层 ======================================================
  // 铁路和后来加的图层（公路 / 产业 / 车辆）共用这一套：按视口加载分块、移出视口就卸载。
  // 原先这段是铁路专用的单例（一个 desiredTileKeys、一个 loadedTiles、一个
  // RAIL_NETWORK_TILES，URL 还写死 /api/rail/tile/），加第二个图层就得整段复制一份、
  // 以后两处还要各自维护。现在每层的差异都收在 spec 里，加载与卸载的逻辑只有一份。
  const extraLayers=[];
  let vehiclesLayer=null;   // 车辆层单独留个引用 —— 它是唯一会"自己动"的图层，需要定时重载
  // 自动刷新**默认关**：车辆层是快照（1296 个点，1154 个是公路车），源数据约 18 秒才重采一轮，
  // 每轮都要重切分块 + 前端重建上千个点，收益很小。想让它动就自己勾上。
  let vehiclesAutoRefresh=false;
  // 边的结构样式：地面常规、隧道虚线、桥加粗偏金色。
  // structure 由 mod 采集时从 BASE_EDGE.type 读出（0 地面 / 1 桥 / 2 隧道），判据是
  // 游戏自己在 res/scripts/selectortooltip.lua 里用的那套。旧数据没有这个字段，
  // 一律按地面画 —— 不会因为缺字段把整张图变样。
  const edgeStructureStyle = (edge, spec) => {
    const base = { 'stroke-width': spec.width || 1, opacity: 1 };
    if (edge.structure === 'TUNNEL') {
      return { ...base, stroke: spec.tunnelColor || '#9b8ae0', 'stroke-dasharray': '4 3', opacity: 0.95 };
    }
    if (edge.structure === 'BRIDGE') {
      return { ...base, stroke: spec.bridgeColor || '#dcc07e', 'stroke-width': (spec.width || 1) * 1.6, opacity: 0.95 };
    }
    return { ...base, stroke: spec.color };
  };
  const createTileLayer=spec=>{
    const loaded=new Map(),pending=new Map();
    let desired=new Set(),visible=spec.visible!==false;
    const renderTile=(key,tile,resource)=>{
      if(!desired.has(key)){resource.remove();return;}
      const entry=spec.render(tile,key);
      entry.resource=resource;loaded.set(key,entry);
      if(spec.onChanged)spec.onChanged();
    };
    const unloadTile=key=>{
      const entry=loaded.get(key);
      if(entry){if(spec.destroy)spec.destroy(entry);else if(entry.group)entry.group.remove();entry.resource.remove();loaded.delete(key);if(spec.onChanged)spec.onChanged();}
      const waiting=pending.get(key);
      if(waiting){waiting.remove();pending.delete(key);}
    };
    const loadTile=key=>{
      if(loaded.has(key)||pending.has(key))return;
      if(location.protocol==='http:'||location.protocol==='https:'){
        const controller=new AbortController(),resource={remove:()=>controller.abort()};pending.set(key,resource);
        fetch(spec.tileUrl(key),{signal:controller.signal,cache:'no-store'}).then(response=>{if(!response.ok)throw new Error(`${spec.name} tile ${key}: ${response.status}`);return response.json();}).then(tile=>{pending.delete(key);renderTile(key,tile,resource);}).catch(error=>{pending.delete(key);if(error.name!=='AbortError')console.error(error);});
        return;
      }
      if(!spec.scriptBase)return;
      const script=document.createElement('script');script.async=true;script.src=`${spec.scriptBase}/tile-${key}.js?v=${spec.version||''}`;
      script.onerror=()=>{pending.delete(key);script.remove();};pending.set(key,script);document.body.appendChild(script);
    };
    // file:// 打开时分块以 <script> 载入并自行派发事件（HTTP 下走 fetch，不经这里）
    if(spec.scriptBase&&spec.globalName&&!spec.scriptBound){
      spec.scriptBound=true;window[spec.globalName]=window[spec.globalName]||{};
      window.addEventListener(spec.scriptEvent,event=>{
        const key=event.detail,tile=window[spec.globalName][key],waiting=pending.get(key);
        if(tile&&waiting)renderTile(key,tile,waiting);
        delete window[spec.globalName][key];pending.delete(key);
      });
    }
    const layer={
      name:spec.name,loaded,
      isVisible:()=>visible,
      // 当前是不是"缩得太远、只画概览骨架"的状态（此时没有分块可重载）
      isSummary:()=>representedMeters()>=spec.thresholdM,
      refreshSummary(){if(visible&&spec.refreshSummary)spec.refreshSummary();},
      update(){
        if(!visible||!spec.manifest)return;
        // 看得比阈值更远（总览）时不加载分块，改由图层自己的概览骨架顶上 ——
        // 铁路的 physical_overview_segments 就是这个角色；没有它，用户在总览下
        // 只会看到空白，容易以为图层没生效。
        if(representedMeters()>=spec.thresholdM){desired=new Set();[...loaded.keys(),...pending.keys()].forEach(unloadTile);if(spec.showSummary)spec.showSummary();return;}
        if(spec.hideSummary)spec.hideSummary();
        const topLeft=worldPoint(0,0),bottomRight=worldPoint(1200,720),margin=spec.tileSizeM*.15;
        const view={minX:Math.min(topLeft.x,bottomRight.x)-margin,maxX:Math.max(topLeft.x,bottomRight.x)+margin,minY:Math.min(topLeft.y,bottomRight.y)-margin,maxY:Math.max(topLeft.y,bottomRight.y)+margin};
        desired=new Set(spec.manifest.tiles.filter(tile=>tile.max.x>=view.minX&&tile.min.x<=view.maxX&&tile.max.y>=view.minY&&tile.min.y<=view.maxY).map(tile=>tile.key));
        [...loaded.keys(),...pending.keys()].filter(key=>!desired.has(key)).forEach(unloadTile);
        desired.forEach(loadTile);
      },
      setVisible(value){
        visible=!!value;
        if(!visible){desired=new Set();[...loaded.keys(),...pending.keys()].forEach(unloadTile);if(spec.hideSummary)spec.hideSummary();}
        else layer.update();
      },
      // 重新拉取"当前已经显示"的分块内容。
      // 为什么需要：源数据（bridge/layer-*.json）由 mod 定时重写、服务端 watch() 会自动重切，
      // 但前端只在首次加载时 fetch 一次 —— 不重拉的话，页面上的车辆永远停在打开那一刻。
      // 做法是「先拿到新数据、再换掉旧的」，不是先卸后拉，避免中间出现空窗闪一下。
      reload(keys){
        if(!visible)return;
        const targets=keys?keys.filter(key=>loaded.has(key)&&desired.has(key)):[...loaded.keys()].filter(key=>desired.has(key));
        targets.forEach(key=>{
          const token=(reloadTokens.get(key)||0)+1;reloadTokens.set(key,token);
          fetch(spec.tileUrl(key),{cache:'no-store'})
            .then(response=>{if(!response.ok)throw new Error(`${spec.name} tile ${key}: ${response.status}`);return response.json();})
            .then(tile=>{
              if(reloadTokens.get(key)!==token||!desired.has(key))return;   // 期间又刷新/已移出视口 → 丢弃这次结果
              const old=loaded.get(key);
              if(old){if(spec.destroy)spec.destroy(old);else if(old.group)old.group.remove();if(old.resource)old.resource.remove();loaded.delete(key);}
              const entry=spec.render(tile,key);
              entry.resource={remove:()=>{}};
              loaded.set(key,entry);
              if(spec.onChanged)spec.onChanged();
            })
            .catch(error=>{if(error.name!=='AbortError')console.error(error);});
        });
      },
    };
    const reloadTokens=new Map();
    return layer;
  };
  const railLayer=createTileLayer({
    name:'rail',manifest:p,
    tileUrl:key=>`/api/rail/tile/${key}`,
    scriptBase:'rail-network-tiles',version:p.generated_at,
    globalName:'RAIL_NETWORK_TILES',scriptEvent:'rail-network-tile',
    thresholdM:p.detail_load_threshold_m,tileSizeM:p.tile_size_m,
    // 分块增删会改变 Pixi 的内容，而 autoStart 已关 —— 必须显式登记一次重绘。
    onChanged:()=>{updateTileStatus();scheduleBridgeRender();schedulePixiRender();},
    render:(tile,key)=>{
      const group=S('g',{'data-tile-key':key},'',detailLayer);
      const tileNodes=new Map(tile.nodes.map(node=>[node.entity_id,node.position]));
      const paths=new Map(tile.edges.map(edge=>[edge.entity_id,edgePath(edge,tileNodes)]));
      if(!pixiApp){
        // 回退分支（Pixi 不可用时才走到）：同样按**样式**合并 —— 理由与 renderExtraTile 里那段相同。
        // 正常路径下铁路走 Pixi，根本不建这些 SVG 元素。
        const railSpec={color:'#83a9bd',width:1,tunnelColor:'#9b8ae0',bridgeColor:'#dcc07e'};
        const buckets=new Map();
        tile.edges.forEach(edge=>{
          const style=edgeStructureStyle(edge,railSpec);
          const key=`${style.stroke}|${style['stroke-width']}|${style['stroke-dasharray']||''}|${style.opacity||1}`;
          let bucket=buckets.get(key);
          if(!bucket){bucket={style,parts:[]};buckets.set(key,bucket);}
          bucket.parts.push(paths.get(edge.entity_id));
        });
        buckets.forEach(bucket=>{
          S('path',{d:bucket.parts.join(''),fill:'none','vector-effect':'non-scaling-stroke','pointer-events':'none',...bucket.style},'',group);
        });
      }
      return {group,tile,tileNodes,paths,pixi:makePixiTile(tile,tileNodes)};
    },
    destroy:entry=>{if(entry.pixi){entry.pixi.container.parent?.removeChild(entry.pixi.container);entry.pixi.container.destroy({children:true});}entry.group.remove();},
  });
  const updateStations=(lightweight=false)=>{
    // 注意：x / y / visibility / pointer-events 这几个是**恒定值**，已经在元素创建时设过一次，
    // 不要在这里每帧重写 —— 原来每帧对 73 个站重复写 4 个固定属性，约 300 次/帧纯浪费。
    stationViews.forEach(view=>{const q=screenPoint(view.station.center);view.screen=q;view.group.setAttribute('transform',`translate(${q.x} ${q.y})`);const selected=selectedStation?.entity_id===view.station.entity_id;view.dot.setAttribute('fill',selected?'#56dcff':'#08141e');view.dot.setAttribute('r',selected?'4.5':'3.2');});
    // 标签这一段是 O(n²)：73 个站两两比包围盒，而且每帧还先排一次序。
    // 它只决定"站名显不显示"，跟平移无关 —— 拖动中整段跳过，松手时 stopDrag 会补一次。
    if(!lightweight){
      const occupied=[];
      const showEveryStationName=representedMeters()<50;
      [...stationViews].sort((a,b)=>Number(b.served)-Number(a.served)||a.station.name.length-b.station.name.length).forEach(view=>{
        const q=view.screen;
        if(q.x<3||q.x>1197||q.y<3||q.y>717||(!view.served&&zoom<2))return;
        // 字号 11 时每个字约占 7 px（原来是 7.5 号字、按 4.8 估），碰撞盒跟着放宽
        const labelWidth=Math.max(18,Array.from(view.station.name).length*7);
        const box={left:q.x+4,right:q.x+8+labelWidth,top:q.y-19,bottom:q.y+2};
        const collides=occupied.some(other=>!(box.right<other.left||box.left>other.right||box.bottom<other.top||box.top>other.bottom));
        if(showEveryStationName||!collides||selectedStation?.entity_id===view.station.entity_id){view.name.setAttribute('visibility','visible');occupied.push(box);}
      });
    }
    depotViews.forEach(view=>{
      const q=screenPoint(view.depot.center),connection=view.depot.track_connection_position?screenPoint(view.depot.track_connection_position):q;
      view.group.setAttribute('transform',`translate(${q.x} ${q.y})`);
      view.group.style.display=q.x>=-10&&q.x<=1210&&q.y>=-10&&q.y<=730?'block':'none';
      Object.entries({x1:q.x,y1:q.y,x2:connection.x,y2:connection.y}).forEach(([key,value])=>view.connector.setAttribute(key,value));
      const showConnector=representedMeters()<300&&Boolean(view.depot.track_connection_position);
      if(view.connectorShown!==showConnector){view.connectorShown=showConnector;view.connector.style.display=showConnector?'block':'none';}
    });
  };
  const updateTrainPositions=()=>{
    // 位置每帧都要更新（车在动），但"显不显示"只取决于 zoom 档位 ——
    // 按元素记下上次的显示状态，只有跨档时才写 style（原来每帧对 72 辆车写 144 次）。
    const meters=representedMeters();
    const showMarker=meters<1500,showLabel=meters<500;
    trainViews.forEach(view=>{
      const q=screenPoint(view.position||view.vehicle.snapped_position||view.vehicle.position);
      view.group.setAttribute('transform',`translate(${q.x} ${q.y})`);
      if(view.markerShown!==showMarker){view.markerShown=showMarker;view.group.style.display=showMarker?'block':'none';}
      if(view.labelShown!==showLabel){view.labelShown=showLabel;view.label.style.display=showLabel?'block':'none';}
    });
  };
  // 把一批船/机落到视图上：**位置更新 + 增删一次做完**（车辆入库/到站要从图上消失）。
  const syncOtherVehicleViews=(views,list)=>{
    const active=new Set();
    (list||[]).forEach(entry=>{
      if(!Number.isFinite(entry.x)||!Number.isFinite(entry.y))return;
      active.add(entry.entity_id);
      let view=views.get(entry.entity_id);
      if(!view){
        const el=S('circle',{r:OTHER_MARK_RADIUS,fill:carrierColor(entry.carrier),
          stroke:'#eaf6ff','stroke-width':.8,'pointer-events':'none'},'',otherVehicleLayer);
        // 新建的船/机点也要立刻遵守当前种类勾选（否则取消勾选"船舶"后新造的船会冒出来）
        el.style.display=carrierVisibleFn(entry.carrier)?'':'none';
        view={el,position:null,carrier:entry.carrier};
        views.set(entry.entity_id,view);
      }
      view.position={x:entry.x,y:entry.y,z:entry.z};
      const q=screenPoint(view.position);
      view.el.setAttribute('cx',q.x.toFixed(1));
      view.el.setAttribute('cy',q.y.toFixed(1));
    });
    views.forEach((view,id)=>{
      if(active.has(id))return;
      view.el.remove();views.delete(id);
    });
  };
  // 船：**90 秒才落一次位**。窗口没到就整批跳过 —— 连位置都不记，免得半路又被更新。
  // （数据其实每 ~1.5 秒来一次，这里主动降频。）
  const syncWaterVehicles=(list)=>{
    const now=performance.now();
    if(waterCommittedAt&&now-waterCommittedAt<WATER_REFRESH_MS)return;
    waterCommittedAt=now;
    syncOtherVehicleViews(waterViews,list);
  };
  const updateOtherVehiclePositions=()=>{
    [airViews,waterViews].forEach(views=>{
      views.forEach(view=>{
        if(!view.position)return;
        const q=screenPoint(view.position);
        view.el.setAttribute('cx',q.x.toFixed(1));
        view.el.setAttribute('cy',q.y.toFixed(1));
      });
    });
  };
  const updateLivePositions=()=>{
    updateTrainPositions();
    updateOtherVehiclePositions();
    signalViews.forEach(view=>{
      const q=screenPoint(view.signal.position);
      view.group.setAttribute('transform',`translate(${q.x} ${q.y})`);
      view.group.style.display=signalsVisible&&representedMeters()<250?'block':'none';
    });
  };
  const stationTitle=station=>stationPreview(station);
  const stopForVehicle=vehicle=>lineById.get(vehicle.line_id)?.stops?.[vehicle.stop_index]||null;
  const vehicleStatus=vehicle=>{
    const stop=stopForVehicle(vehicle),station=stop?stationById.get(stop.station_group_id):null;
    if(vehicle.raw_state===2)return `到站${station?.name||''}`;
    if((vehicle.speed_kmh??0)<1)return '等待区间';
    return '预计正点';
  };
  const stationForVehicle=vehicle=>{
    const target=stopForVehicle(vehicle);
    if(vehicle.raw_state===2&&target)return stationById.get(target.station_group_id)||null;
    return (stationsByPlatformEdge.get(vehicle.edge_id)||[])[0]||null;
  };
  const formatSystemTime=value=>new Date(value).toLocaleString('zh-CN',{hour12:false,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit'});
  const formatStationLogTime=value=>{
    const date=new Date(value),two=part=>String(part).padStart(2,'0');
    return `${two(date.getMonth()+1)}-${two(date.getDate())} ${two(date.getHours())}:${two(date.getMinutes())}`;
  };
  const workLogStatus={
    EXECUTED:{label:'已执行',className:'applied'},
    BLOCKED:{label:'被阻挡',className:'blocked'},
    PENDING:{label:'待处理',className:'pending'},
    CANCELLED:{label:'已取消',className:'cancelled'},
    TEST:{label:'系统测试',className:'planned'},
  };
  const workLogActionLabels={
    BUY_VEHICLE:'购买车辆',ASSIGN_VEHICLE_TO_LINE:'车辆分配到线路',SET_LINE_STOP_POLICY:'调整停站策略',SET_LINE_STOPS:'调整线路停靠站台',CREATE_LINE:'创建线路',CREATE_LINE_FROM_SOURCE_ROUTE:'创建线路',SELL_VEHICLE:'出售车辆',RENAME_LINE:'重命名线路',HOLD_VEHICLE:'扣停列车',HOLD_VEHICLE_AT_TERMINAL:'扣停列车',RELEASE_VEHICLE:'放行列车',TIMETABLE_PLAN_GENERATED:'运行图系统测试',
  };
  const workLogCategory=item=>item.category||(item.applied?'EXECUTED':'TEST');
  const workLogTarget=item=>[Number.isInteger(item.line_id)?`线路 ${item.line_id}`:'',Number.isInteger(item.vehicle_id)?`车辆 ${item.vehicle_id}`:'',item.task_id?`任务 ${item.task_id}`:''].filter(Boolean).join(' · ')||'全路网';
  const closeWorkLogModal=()=>{
    if(!workLogModal)return;
    workLogModal.remove();workLogModal=null;
    if(workLogReturnFocus?.focus)workLogReturnFocus.focus();
    workLogReturnFocus=null;
  };
  const renderWorkLogModal=()=>{
    if(!workLogModal)return;
    const entries=allMcpWorkLog.entries||[],counts={ALL:entries.length};
    Object.keys(workLogStatus).forEach(category=>{counts[category]=entries.filter(item=>workLogCategory(item)===category).length;});
    workLogModal.querySelectorAll('[data-work-log-filter]').forEach(button=>{
      const category=button.dataset.workLogFilter,label=category==='ALL'?'全部':workLogStatus[category]?.label||category;
      button.textContent=`${label} ${counts[category]||0}`;
      button.classList.toggle('active',category===workLogFilter);
      button.setAttribute('aria-pressed',String(category===workLogFilter));
    });
    const query=workLogSearch.trim().toLocaleLowerCase('zh-CN');
    const visible=entries.filter(item=>(workLogFilter==='ALL'||workLogCategory(item)===workLogFilter)&&(!query||[item.summary,item.action_type,item.reason,item.line_id,item.vehicle_id,item.task_id,item.task_status].some(value=>String(value??'').toLocaleLowerCase('zh-CN').includes(query))));
    templates.setText(workLogModal,'work-log-summary',`显示 ${visible.length} 条，共 ${entries.length} 条`);
    const slot=templates.slot(workLogModal,'work-log-entries'),rows=[];
    if(workLogRequestPending)rows.push(templates.message('WAIT','正在读取全部工作日志'));
    else if(workLogLoadError)rows.push(templates.message('ERROR',workLogLoadError,true));
    else visible.forEach(item=>{
      const category=workLogCategory(item),meta=workLogStatus[category]||{label:category,className:'pending'};
      const row=templates.instantiate('work-log-detail-row-template'),status=templates.setText(row,'status',meta.label);
      status.classList.add(`status-${category.toLowerCase()}`);
      templates.setText(row,'time',formatSystemTime(item.occurred_at*1000));
      templates.setText(row,'summary',item.summary||workLogActionLabels[item.action_type]||item.action_type);
      templates.setText(row,'action',workLogActionLabels[item.action_type]||item.action_type||'UNKNOWN');
      templates.setText(row,'target',workLogTarget(item));
      templates.setText(row,'reason',`状态依据：${item.reason||item.verification_status||item.task_status||'UNKNOWN'}`);
      rows.push(row);
    });
    if(!rows.length)rows.push(templates.message('NONE','当前筛选条件下没有记录'));
    slot.replaceChildren(...rows);
  };
  const openWorkLogModal=()=>{
    if(workLogModal)return;
    workLogReturnFocus=document.activeElement;
    workLogFilter='ALL';workLogSearch='';workLogLoadError=null;allMcpWorkLog={entries:[]};
    workLogModal=templates.instantiate('work-log-modal-template');
    workLogModal.querySelectorAll('[data-action="work-log-close"]').forEach(button=>button.addEventListener('click',closeWorkLogModal));
    workLogModal.querySelectorAll('[data-work-log-filter]').forEach(button=>button.addEventListener('click',()=>{workLogFilter=button.dataset.workLogFilter;renderWorkLogModal();}));
    const search=workLogModal.querySelector('[data-action="work-log-search"]');
    search.addEventListener('input',()=>{workLogSearch=search.value;renderWorkLogModal();});
    document.body.appendChild(workLogModal);search.focus();
    workLogRequestPending=true;renderWorkLogModal();
    fetch('/api/mcp-work-log?limit=all',{cache:'no-store'}).then(response=>{if(!response.ok)throw new Error(`mcp-work-log: ${response.status}`);return response.json();}).then(value=>{allMcpWorkLog=value;}).catch(error=>{console.error(error);workLogLoadError='读取工作日志失败';}).finally(()=>{workLogRequestPending=false;renderWorkLogModal();});
  };
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&workLogModal)closeWorkLogModal();});
  const stationRoutes=station=>{const ids=new Set(relatedStations(station).map(item=>item.entity_id));return p.lines.filter(line=>line.stops.some(stop=>ids.has(stop.station_group_id)));};
  const stationServingVehicleCount=routes=>{
    const liveCounts=new Map();
    (liveState?.vehicles||[]).forEach(vehicle=>{
      if(Number.isInteger(vehicle.line_id))liveCounts.set(vehicle.line_id,(liveCounts.get(vehicle.line_id)||0)+1);
    });
    return routes.reduce((total,line)=>{
      const configured=operationLineById.get(line.entity_id)?.vehicle_count;
      return total+(Number.isFinite(configured)?configured:(liveCounts.get(line.entity_id)||0));
    },0);
  };
  const currentSimulationSpeedLabel=()=>{
    const multiplier=Number(liveState?.simulation?.speed_multiplier);
    return Number.isFinite(multiplier)?`${multiplier}x`:'?x';
  };
  const dwellDescription=(line,station)=>{
    const ids=new Set(relatedStations(station).map(item=>item.entity_id));
    const op=operationLineById.get(line.entity_id),stops=(op?.stops||[]).filter(stop=>ids.has(stop.station_id));
    if(!stops.length)return '停留时间待采';
    return stops.map(stop=>{
      const scheduled=Number.isFinite(stop.scheduled_dwell_seconds)?`${Math.round(stop.scheduled_dwell_seconds)}秒`:'待生成';
      return `第${Number(stop.sequence_index)+1}站 图定停车${scheduled}(${currentSimulationSpeedLabel()})`;
    }).join('\n');
  };
  const $sidebarBack=$('#sidebar-back');
  const setSidebarBackVisible=visible=>$sidebarBack.toggleClass('is-hidden',!visible);
  const renderOverviewSidebar=()=>{
    setSidebarBackVisible(false);
    const sidebar=templates.instantiate('overview-sidebar-template');
    const lineSlot=templates.slot(sidebar,'lines');
    p.lines.forEach(line=>{
      const row=templates.instantiate('route-row-template');
      templates.setText(row,'name',line.name);
      templates.setText(row,'stop-count',`${line.stops.length} 站`);
      lineSlot.appendChild(row);
    });
    const orderedSuggestions=[...(aiAdvice.suggestions||[])].sort((a,b)=>(Number(b.created_at)||0)-(Number(a.created_at)||0));
    const visibleSuggestions=orderedSuggestions.slice(0,aiAdviceVisibleCount);
    const suggestionSlot=templates.slot(sidebar,'suggestions');
    visibleSuggestions.forEach(item=>{
      const row=templates.instantiate('suggestion-row-template');
      if(item.severity==='ACTION')row.classList.add('action');
      templates.setText(row,'time',item.created_at?formatSystemTime(item.created_at*1000):'时间 UNKNOWN');
      templates.setText(row,'label',item.template_label||item.template);
      templates.setText(row,'title',item.title);
      templates.setText(row,'detail',[item.reason,item.required_action].filter(Boolean).join('\n'));
      suggestionSlot.appendChild(row);
    });
    const moreCount=Math.max(0,orderedSuggestions.length-visibleSuggestions.length);
    if(moreCount){
      const more=templates.instantiate('advice-more-template');
      more.textContent=`查看更多（剩余 ${moreCount} 条）`;
      more.addEventListener('click',()=>{aiAdviceVisibleCount+=10;renderOverviewSidebar();});
      suggestionSlot.appendChild(more);
    }else if(!visibleSuggestions.length){
      suggestionSlot.appendChild(templates.message('CLEAR','当前没有需要人工处理的运行图建议'));
    }
    const workSlot=templates.slot(sidebar,'work-log'),entries=(mcpWorkLog.entries||[]).slice(0,12);
    entries.forEach(item=>{
      const category=workLogCategory(item),meta=workLogStatus[category]||{label:category,className:'planned'};
      const row=templates.instantiate('work-entry-template'),result=templates.setText(row,'result',meta.label);
      result.classList.add(meta.className);
      templates.setText(row,'time',formatSystemTime(item.occurred_at*1000));
      templates.setText(row,'summary',item.summary);
      workSlot.appendChild(row);
    });
    if(!entries.length)workSlot.appendChild(templates.message('WAIT','暂无MCP调整记录'));
    sidebar.querySelector('[data-action="work-log-all"]').addEventListener('click',openWorkLogModal);
    document.querySelector('#sidebar').replaceChildren(sidebar);
  };
  const returnToOverview=()=>{selectedStation=null;selectedVehicleId=null;vehicleDetail=null;stationLogRows=[];document.querySelector('#station-name').textContent='全路网';renderOverviewSidebar();updateStations();};
  $sidebarBack.off('.sidebarBack').on('click.sidebarBack',returnToOverview);
  const stationFacilityKind=groups=>{
    const kinds=groups.map(group=>{const terminals=group.terminals||[];return {passenger:terminals.some(terminal=>!terminal.cargo),cargo:terminals.some(terminal=>terminal.cargo)};});
    const passenger=kinds.some(kind=>kind.passenger),cargo=kinds.some(kind=>kind.cargo);
    if(passenger&&cargo)return kinds.some(kind=>kind.passenger&&kind.cargo)?'客货混用车站':'客货车站';
    return passenger?'客运车站':cargo?'货运车站':'未知车站';
  };
  const stationSidebarData=station=>{
    const groups=relatedStations(station),groupIds=new Set(groups.map(item=>item.entity_id)),routes=stationRoutes(station);
    const vehicles=(liveState?.vehicles||[]).filter(vehicle=>groupIds.has(stationForVehicle(vehicle)?.entity_id)||(vehicle.raw_state===2&&groupIds.has(stopForVehicle(vehicle)?.station_group_id)));
    const platforms=groups.flatMap(physicalPlatforms);
    const platformFaces=platforms.reduce((total,platform)=>total+Math.max(1,(platform.terminal_faces||[]).length),0);
    // 互通站群：同一片里的车站算一个整体，所以规模（线路数、在跑的车）也按整片合计，
    // 而不是只数本站。这正是"算客流要综合考虑"的第一步 —— 换乘的人流会在这片里流动。
    // 包一层 try：带 ?station=xxx 进页面时，初始化阶段就会渲染侧边栏，而站群模块
    // 在这段代码之后才定义（const 的暂时性死区），此时应当退化成"没有站群信息"而不是报错。
    let cluster=null;
    try{cluster=stationClusterInfo(station);}catch(error){cluster=null;}
    const summaryParts=[`${stationFacilityKind(groups)} ${platformFaces}站台`];
    if(cluster&&cluster.memberCount>1){
      summaryParts.push(`互通 ${cluster.memberCount} 站`);
      if(cluster.lineCount!=null)summaryParts.push(`该片合计 ${cluster.lineCount} 线`);
      if(cluster.vehicleCount!=null)summaryParts.push(`${cluster.vehicleCount} 车`);
    }
    return {groups,routes,vehicles,platforms,platformFaces,cluster,
            summary:summaryParts.join(' · '),servingVehicles:stationServingVehicleCount(routes)};
  };
  const fillStationRoutes=(slot,station,routes)=>{
    const rows=routes.map(line=>{const row=templates.instantiate('station-route-row-template');templates.setText(row,'name',line.name);templates.setText(row,'dwell',dwellDescription(line,station));return row;});
    if(!rows.length)rows.push(templates.message('NONE','当前没有线路办理停靠',true));
    slot.replaceChildren(...rows);
  };
  // 列表原地复用：同一个 key 复用同一 DOM 节点，只改文字。
  // 原实现每次轮询都 replaceChildren 整块列表，导致页面每 0.5 秒闪一次。
  const reconcileRows=(slot,items,{keyOf,build,apply})=>{
    [...slot.children].forEach(node=>{if(!node.dataset.rowKey)node.remove();});
    const existing=new Map();
    [...slot.children].forEach(node=>{if(node.dataset.rowKey)existing.set(node.dataset.rowKey,node);});
    const keep=new Set();
    items.forEach(item=>{
      const key=String(keyOf(item));
      keep.add(key);
      let row=existing.get(key);
      if(!row){row=build(item);row.dataset.rowKey=key;slot.appendChild(row);}
      apply(row,item);
    });
    existing.forEach((node,key)=>{if(!keep.has(key))node.remove();});
  };
  const fillStationLiveVehicles=(slot,vehicles)=>{
    if(!vehicles.length){
      if(slot.dataset.mode!=='empty'){slot.dataset.mode='empty';slot.replaceChildren(templates.message('CLEAR','当前站界内无列车'));}
      return;
    }
    slot.dataset.mode='list';
    reconcileRows(slot,vehicles,{
      keyOf:vehicle=>vehicle.entity_id,
      build:vehicle=>{
        const row=templates.instantiate('station-live-vehicle-row-template');
        row.dataset.vehicleId=vehicle.entity_id;
        row.addEventListener('click',()=>{selectedStation=null;selectedVehicleId=Number(row.dataset.vehicleId);vehicleDetail=null;vehicleDetailLoadedAt=0;renderVehicleSidebar();loadVehicleDetail();updateStations();});
        return row;
      },
      apply:(row,vehicle)=>{
        templates.setText(row,'name',vehicle.name||`列车${vehicle.entity_id}`);
        templates.setText(row,'motion',`${Math.round(vehicle.speed_kmh??0)} km/h · ${vehicleStatus(vehicle)}`);
      }
    });
  };
  const stationLogKey=item=>[item.observed_at,item.line_id,item.vehicle_id??item.vehicle_name,item.event_type].join(':');
  const fillStationLogs=slot=>{
    // 内容没变就不重建：车站日志每 2 秒刷新一次，整块重建会让日志区闪烁。
    const logsKey=stationLogRows.map(stationLogKey).join('|');
    if(slot.dataset.logsKey===logsKey)return;
    slot.dataset.logsKey=logsKey;
    const previousTop=slot.scrollTop;
    const anchor=[...slot.children].find(row=>row.offsetTop+row.offsetHeight>previousTop);
    const anchorKey=anchor?.dataset.logKey,anchorOffset=anchor?anchor.offsetTop-previousTop:0;
    const rows=stationLogRows.map(item=>{const row=templates.instantiate('station-log-row-template');row.dataset.logKey=stationLogKey(item);if(item.event_type==='PASS')row.classList.add('warn');templates.setText(row,'time',formatStationLogTime(item.observed_at*1000));templates.setText(row,'event',`${item.line_name} ${item.vehicle_name} ${item.event_type==='STOP'?'停靠':'跨站'}`);return row;});
    if(!rows.length)rows.push(templates.message('WAIT','暂无已记录的到发事件'));
    slot.replaceChildren(...rows);
    if(previousTop<=1){slot.scrollTop=previousTop;return;}
    const nextAnchor=anchorKey?[...slot.children].find(row=>row.dataset.logKey===anchorKey):null;
    slot.scrollTop=nextAnchor?nextAnchor.offsetTop-anchorOffset:Math.min(previousTop,Math.max(0,slot.scrollHeight-slot.clientHeight));
  };
  const currentStationSidebar=()=>document.querySelector('#sidebar > .station-sidebar');
  const refreshStationLiveSidebar=()=>{
    if(!selectedStation)return;
    const sidebar=currentStationSidebar();
    if(!sidebar){renderStationSidebar();return;}
    const data=stationSidebarData(selectedStation);
    templates.setText(sidebar,'serving-vehicles',`图定停靠 ${data.servingVehicles} 趟列车`);
    fillStationLiveVehicles(templates.slot(sidebar,'live-vehicles'),data.vehicles);
    const speedLabel=currentSimulationSpeedLabel();
    if(sidebar.dataset.dwellSpeed!==speedLabel){fillStationRoutes(templates.slot(sidebar,'routes'),selectedStation,data.routes);sidebar.dataset.dwellSpeed=speedLabel;}
  };
  const refreshStationOperationsSidebar=()=>{
    if(!selectedStation)return;
    const sidebar=currentStationSidebar();
    if(!sidebar){renderStationSidebar();return;}
    const data=stationSidebarData(selectedStation),title=stationTitle(selectedStation);
    templates.setText(sidebar,'station-name',title);
    templates.setText(sidebar,'station-summary',data.summary);
    templates.setText(sidebar,'serving-vehicles',`图定停靠 ${data.servingVehicles} 趟列车`);
    fillStationRoutes(templates.slot(sidebar,'routes'),selectedStation,data.routes);
    sidebar.dataset.dwellSpeed=currentSimulationSpeedLabel();
    document.querySelector('#station-name').textContent=title;
  };
  const refreshStationLogSidebar=()=>{
    if(!selectedStation)return;
    const sidebar=currentStationSidebar();
    if(!sidebar){renderStationSidebar();return;}
    fillStationLogs(templates.slot(sidebar,'logs'));
  };
  const renderStationSidebar=()=>{
    if(!selectedStation){renderOverviewSidebar();return;}
    setSidebarBackVisible(true);
    const station=selectedStation,{routes,vehicles,summary,servingVehicles}=stationSidebarData(station);
    const sidebar=templates.instantiate('station-sidebar-template');
    templates.setText(sidebar,'station-name',stationTitle(station));
    templates.setText(sidebar,'station-summary',summary);
    templates.setText(sidebar,'serving-vehicles',`图定停靠 ${servingVehicles} 趟列车`);
    fillStationRoutes(templates.slot(sidebar,'routes'),station,routes);
    sidebar.dataset.dwellSpeed=currentSimulationSpeedLabel();
    fillStationLiveVehicles(templates.slot(sidebar,'live-vehicles'),vehicles);
    fillStationLogs(templates.slot(sidebar,'logs'));
    document.querySelector('#sidebar').replaceChildren(sidebar);
    document.querySelector('#station-name').textContent=stationTitle(station);
  };
  const renderVehicleSidebar=()=>{
    if(selectedVehicleId==null){renderOverviewSidebar();return;}
    setSidebarBackVisible(true);
    const live=(liveState?.vehicles||[]).find(item=>item.entity_id===selectedVehicleId)||{},detail=vehicleDetail||{},vehicle=detail.vehicle||{},load=detail.load||{},next=detail.next_stop||{};
    const name=live.name||vehicle.name||`列车${selectedVehicleId}`,line=lineById.get(live.line_id??vehicle.line_id),speed=live.speed_kmh??detail.motion?.speed_kmh;
    const loadText=vehicleDetailPending&&!vehicleDetail?'读取中…':load.total==null?'UNKNOWN':`${load.total} / ${load.capacity??'—'}`;
    const sidebar=templates.instantiate('vehicle-sidebar-template');
    templates.setText(sidebar,'vehicle-name',name);
    templates.setText(sidebar,'vehicle-id',selectedVehicleId);
    templates.setText(sidebar,'line-name',line?.name||vehicle.line_name||'UNKNOWN');
    templates.setText(sidebar,'speed',speed==null?'UNKNOWN':`${Math.round(speed)} km/h`);
    templates.setText(sidebar,'status',vehicleStatus({...live,line_id:live.line_id??vehicle.line_id}));
    templates.setText(sidebar,'next-station',next.station_name||stopForVehicle(live)?.station_group_name||'UNKNOWN');
    templates.setText(sidebar,'total-load',loadText);
    templates.setText(sidebar,'passengers',load.passengers??'—');
    templates.setText(sidebar,'cargo',load.cargo??'—');
    templates.setText(sidebar,'block',live.block_id||detail.motion?.block_id||'UNKNOWN');
    templates.setText(sidebar,'position-source',live.position_source||'UNKNOWN');
    templates.setText(sidebar,'position-stale',live.position_stale?'是':'否');
    const cargoSlot=templates.slot(sidebar,'cargo-types');
    (load.cargo_by_type||[]).forEach(item=>{const row=templates.instantiate('cargo-row-template');templates.setText(row,'cargo-name',item.cargo_name||`货物 ${item.cargo_id}`);templates.setText(row,'amount',item.amount);cargoSlot.appendChild(row);});
    if(detail.availability?.load===false)templates.slot(sidebar,'load-status').appendChild(templates.message('UNKNOWN','当前装载数据暂不可用',true));
    document.querySelector('#sidebar').replaceChildren(sidebar);
    document.querySelector('#station-name').textContent=name;
  };
  // 车辆侧栏的原地刷新：与车站侧栏一样只改文字，不重建 DOM。
  // 原实现每 0.5 秒 replaceChildren 整个 #sidebar，是页面频闪的主因。
  const refreshVehicleLiveSidebar=()=>{
    const sidebar=document.querySelector('#sidebar > .vehicle-sidebar');
    if(!sidebar){renderVehicleSidebar();return;}
    const live=(liveState?.vehicles||[]).find(item=>item.entity_id===selectedVehicleId)||{},detail=vehicleDetail||{},vehicle=detail.vehicle||{},load=detail.load||{},next=detail.next_stop||{};
    const name=live.name||vehicle.name||`列车${selectedVehicleId}`,speed=live.speed_kmh??detail.motion?.speed_kmh;
    templates.setText(sidebar,'vehicle-name',name);
    templates.setText(sidebar,'vehicle-id',selectedVehicleId);
    templates.setText(sidebar,'line-name',lineById.get(live.line_id??vehicle.line_id)?.name||vehicle.line_name||'UNKNOWN');
    templates.setText(sidebar,'speed',speed==null?'UNKNOWN':`${Math.round(speed)} km/h`);
    templates.setText(sidebar,'status',vehicleStatus({...live,line_id:live.line_id??vehicle.line_id}));
    templates.setText(sidebar,'next-station',next.station_name||stopForVehicle(live)?.station_group_name||'UNKNOWN');
    templates.setText(sidebar,'total-load',vehicleDetailPending&&!vehicleDetail?'读取中…':load.total==null?'UNKNOWN':`${load.total} / ${load.capacity??'—'}`);
    templates.setText(sidebar,'passengers',load.passengers??'—');
    templates.setText(sidebar,'cargo',load.cargo??'—');
    templates.setText(sidebar,'block',live.block_id||detail.motion?.block_id||'UNKNOWN');
    templates.setText(sidebar,'position-source',live.position_source||'UNKNOWN');
    templates.setText(sidebar,'position-stale',live.position_stale?'是':'否');
    document.querySelector('#station-name').textContent=name;
    // 结构部分（货种明细、装载不可用提示）只在内容真的变了时才重建。
    const cargoKey=`${(load.cargo_by_type||[]).map(item=>`${item.cargo_id}:${item.amount}`).join('|')}#${detail.availability?.load===false?'x':'ok'}`;
    if(sidebar.dataset.cargoKey!==cargoKey){
      sidebar.dataset.cargoKey=cargoKey;
      const cargoSlot=templates.slot(sidebar,'cargo-types');
      cargoSlot.replaceChildren();
      (load.cargo_by_type||[]).forEach(item=>{const row=templates.instantiate('cargo-row-template');templates.setText(row,'cargo-name',item.cargo_name||`货物 ${item.cargo_id}`);templates.setText(row,'amount',item.amount);cargoSlot.appendChild(row);});
      const statusSlot=templates.slot(sidebar,'load-status');
      statusSlot.replaceChildren();
      if(detail.availability?.load===false)statusSlot.appendChild(templates.message('UNKNOWN','当前装载数据暂不可用',true));
    }
  };
  const loadVehicleDetail=()=>{
    if(selectedVehicleId==null||vehicleDetailPending||Date.now()-vehicleDetailLoadedAt<5000||!(location.protocol==='http:'||location.protocol==='https:'))return;
    const requestedId=selectedVehicleId;vehicleDetailPending=true;refreshVehicleLiveSidebar();
    fetch(`/api/vehicle-detail/${requestedId}`,{cache:'no-store'}).then(response=>{if(!response.ok)throw new Error(`vehicle-detail: ${response.status}`);return response.json();}).then(value=>{if(selectedVehicleId!==requestedId)return;vehicleDetail=value;vehicleDetailLoadedAt=Date.now();refreshVehicleLiveSidebar();}).catch(error=>{console.error(error);if(selectedVehicleId===requestedId){vehicleDetail={availability:{load:false}};refreshVehicleLiveSidebar();}}).finally(()=>{vehicleDetailPending=false;});
  };
  const loadStationLogs=()=>{
    if(!selectedStation||stationLogRequestPending||!(location.protocol==='http:'||location.protocol==='https:'))return;
    const requestedId=selectedStation.entity_id,ids=relatedStations(selectedStation).map(item=>item.entity_id);stationLogRequestPending=true;
    Promise.all(ids.map(id=>fetch(`/api/station-logs/${id}?limit=100`,{cache:'no-store'}).then(response=>{if(!response.ok)throw new Error(`station-logs: ${response.status}`);return response.json();}))).then(values=>{if(selectedStation?.entity_id!==requestedId)return;stationLogRows=values.flatMap(value=>value.events||[]).sort((a,b)=>b.observed_at-a.observed_at).slice(0,100);refreshStationLogSidebar();}).catch(error=>console.error(error)).finally(()=>{stationLogRequestPending=false;});
  };
  const reconcileLive=value=>{
    const hasVehicles=Object.prototype.hasOwnProperty.call(value,'vehicles');
    if(hasVehicles)liveState=value;
    if(value.simulation){
      const simulation=value.simulation,multiplier=Number(simulation.speed_multiplier),clock=document.querySelector('.clock');
      if(clock){
        const clockText=simulation.status==='PAUSED'||simulation.status==='PAUSED_OR_STALLED'
          ?'已暂停'
          :(simulation.status==='RUNNING'||simulation.status==='RUNNING_INFERRED')&&Number.isFinite(multiplier)
            ?`运行中 ${multiplier}×`
            :'运行状态 UNKNOWN';
        if(clock.textContent!==clockText)clock.textContent=clockText;
      }
    }
    if(hasVehicles){
     const sampleAt=Number(value.sampled_at)||performance.now()/1000;
     const isNewFrame=lastVehicleSampleAt==null||sampleAt>lastVehicleSampleAt;
     const activeTrains=new Set((value.vehicles||[]).map(vehicle=>vehicle.entity_id));
     trainViews.forEach((view,id)=>{
       if(activeTrains.has(id))return;
       const missingSeconds=Math.max(0,sampleAt-(view.lastSeenAt??sampleAt));
       if(missingSeconds>30){view.group.remove();trainViews.delete(id);return;}
       view.frontendStale=true;view.marker.setAttribute('fill','#ffd34f');view.marker.setAttribute('stroke','#66e2ff');view.marker.setAttribute('stroke-width','2');
     });
     (value.vehicles||[]).forEach(vehicle=>{
      let view=trainViews.get(vehicle.entity_id);
      if(!view){
        const group=S('g',{'data-vehicle-id':vehicle.entity_id,cursor:'pointer'},'',liveLayer);
        const marker=S('path',{d:'M0,-5 L4,0 L0,5 L-4,0 Z',fill:'#ffd34f',stroke:'#2a1a00','stroke-width':1.2},'',group);
        const label=S('text',{x:7,y:3,fill:'#ffe89a','font-size':8,'font-family':'Consolas, Microsoft YaHei','paint-order':'stroke',stroke:'#071019','stroke-width':2},'',group);
        const show=event=>{const current=group.__vehicle,speed=current.speed_kmh==null?'—':Math.round(current.speed_kmh),stale=current.position_stale||group.__view?.frontendStale?` · 隧道/路径边界定位保持 ${current.position_age_seconds??'—'}s`:'';tooltip.textContent=`${current.name||'列车 '+current.entity_id}-${speed}-${vehicleStatus(current)}${stale}`;tooltip.style.display='block';moveTooltip(event);};
        group.addEventListener('pointerenter',show);group.addEventListener('pointermove',show);group.addEventListener('pointerleave',()=>{tooltip.style.display='none';});group.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();selectedStation=null;selectedVehicleId=group.__vehicle.entity_id;vehicleDetail=null;vehicleDetailLoadedAt=0;renderVehicleSidebar();loadVehicleDetail();updateStations();});
        const target=vehicle.snapped_position||vehicle.position;
        view={group,marker,label,vehicle,position:target,sampledAt:sampleAt,lastSeenAt:sampleAt,frontendStale:false};group.__view=view;trainViews.set(vehicle.entity_id,view);
      }else if(isNewFrame&&view.sampledAt!==sampleAt){
        view.position=vehicle.snapped_position||vehicle.position;
        view.sampledAt=sampleAt;
      }
      view.vehicle=vehicle;view.group.__vehicle=vehicle;view.lastSeenAt=sampleAt;view.frontendStale=false;view.label.textContent=`${vehicle.name||`列车${vehicle.entity_id}`}-${vehicle.speed_kmh==null?'—':Math.round(vehicle.speed_kmh)}-${vehicleStatus(vehicle)}`;
      const stale=Boolean(vehicle.position_stale);view.marker.setAttribute('fill','#ffd34f');view.marker.setAttribute('stroke',stale?'#66e2ff':'#2a1a00');view.marker.setAttribute('stroke-width',stale?'2':'1.2');
     });
     // 船 / 飞机：位置来自服务端的 air_vehicles / water_vehicles（包围盒中心，不吸附轨道）。
     // 飞机每次新帧都跟（与列车同频）；船走 90 秒节流。
     if(Array.isArray(value.air_vehicles))syncOtherVehicleViews(airViews,value.air_vehicles);
     if(Array.isArray(value.water_vehicles))syncWaterVehicles(value.water_vehicles);
     if(isNewFrame)lastVehicleSampleAt=sampleAt;
    }
    if(Object.prototype.hasOwnProperty.call(value,'signals')){
     const activeSignals=new Set((value.signals||[]).map((signal,index)=>`${signal.entity_id??'x'}:${signal.edge_id}:${index}`));
     signalViews.forEach((view,id)=>{if(!activeSignals.has(id)){view.group.remove();signalViews.delete(id);}});
     (value.signals||[]).forEach((signal,index)=>{
      const id=`${signal.entity_id??'x'}:${signal.edge_id}:${index}`;
      if(signalViews.has(id)){signalViews.get(id).signal=signal;return;}
      const group=S('g',{'data-signal-id':id,cursor:'help'},'',liveLayer);
      const candidate=signal.source_status==='TRACK_OBJECT_CANDIDATE';
      S('path',{d:'M-3,4 L0,-4 L3,4 Z',fill:candidate?'#ffbd52':'#ff5968',stroke:candidate?'#fff0bd':'#ffd3d7','stroke-width':.8},'',group);
      group.addEventListener('pointerenter',event=>{tooltip.textContent=`${candidate?'轨道控制设备候选':'信号机'} · Edge ${signal.edge_id} · 灯色 UNKNOWN`;tooltip.style.display='block';moveTooltip(event);});
      group.addEventListener('pointermove',moveTooltip);group.addEventListener('pointerleave',()=>{tooltip.style.display='none';});
      signalViews.set(id,{group,signal});
     });
    }
    updateLivePositions();
    if(selectedStation&&hasVehicles)refreshStationLiveSidebar();else if(selectedVehicleId!=null&&hasVehicles){refreshVehicleLiveSidebar();loadVehicleDetail();}
  };
  // POINT 类图层的图标（车辆等）：尺寸要和列车菱形（`M0,-5 L4,0 L0,5 L-4,0 Z`＝8×10 px）
  // 一致 —— 也就是**屏幕固定尺寸**，不能随地图缩放变大变小。
  // 这些点挂在 mapLayer 里（位置用 P() 底图坐标、跟着地图走是对的），但尺寸会被
  // mapLayer 的 scale(zoom) 一起放大，所以给每个点补一个反向缩放。
  //
  // 🔴 反向缩放是 **1/zoom**，**不是** 1/(baseScale*zoom)。
  //    P() 的输出已经是【底图坐标】（世界坐标在 P() 里就乘过 baseScale 了），
  //    元素进了 mapLayer 之后，底图 → 屏幕**只乘 zoom**。多乘一个 baseScale 会让
  //    屏幕尺寸变成 baseScale 分之一 —— 本机 baseScale≈0.0443，也就是**放大 22.6 倍**，
  //    4 px 的圆变成 90 px（2026-09-29 实测踩过：满屏巨圆把地图盖住）。
  //    验证：屏幕尺寸 = r × (1/zoom) × zoom = r，与 zoom 和 baseScale 都无关 ✓
  //
  // ⚠ 只在 zoom 变化时重算：平移不改变这个比例，每帧写上千个属性会掉帧。
  const pointMarks=new Map();        // 元素 → {x, y}（底图坐标）
  let lastMarkScale=null;
  const refreshPointMarks=()=>{
    const s=1/zoom;
    if(s===lastMarkScale)return;
    lastMarkScale=s;
    pointMarks.forEach((item,el)=>{
      el.setAttribute('transform',`translate(${item.x.toFixed(1)} ${item.y.toFixed(1)}) scale(${s.toFixed(4)})`);
    });
  };
  // 登记一个点：半径按"屏幕像素"给，位置仍用底图坐标
  const addPointMark=(el,x,y)=>{
    pointMarks.set(el,{x,y});
    const s=lastMarkScale!=null?lastMarkScale:1/zoom;
    el.setAttribute('transform',`translate(${x.toFixed(1)} ${y.toFixed(1)}) scale(${s.toFixed(4)})`);
    lastMarkScale=s;
  };
  const dropPointMarks=marks=>{if(marks)marks.forEach(el=>pointMarks.delete(el));};
  // lightweight=true 时只做"平移必须做的那几件"，其余等松手再补一次。
  // 为什么需要：拖动中每帧都要跑这个函数，而下面这些跟"平移"无关的重活占了大头 ——
  //   ① updateMapDetailVisibility / 各 tile 层 update()：算的是"要不要加载新分块"。
  //      拖动中用户还在移动，此刻加载的块很可能马上又要卸掉 —— 纯浪费，等松手再算。
  //   ② refreshContoursOnViewChange()：等高线只跟**缩放**有关，平移不影响它。
  //   ③ updateStations 里的标签排序与碰撞检测：只决定"站名显不显示"，而且是 O(n²)
  //      （73 个站两两比包围盒）—— 拖动中跳过，松手补上。
  // 屏幕坐标的元素（车站点、列车、信号、停站标记）**必须每帧更新**，
  // 否则它们会黏在原地而地图在动 —— 所以那几项无论如何都跑。
  // 外部扩展（独立文件：站点结构 station-struct.js / 产业链流向 freight-flow.js）
  // 注册的**每帧回调**。它们需要跟着地图重算屏幕坐标，所以挂到这里 —— 而不是各写一个
  // requestAnimationFrame（那样会跟地图的绘制节奏脱节，拖动时标记会滞后一拍）。
  const viewportHooks=[];
  const updateViewport=(lightweight=false)=>{
    mapLayer.setAttribute('transform',`translate(${panX} ${panY}) translate(600 360) scale(${zoom}) translate(-600 -360)`);
    document.querySelector('#zoom-value').textContent=`${Math.round(zoom*100)}%`;
    document.querySelector('#zoom-out').disabled=zoom<=1+1e-9;
    scaleText.textContent=formatDistance(representedMeters());
    if(!lightweight)updateMapDetailVisibility();
    updateStations(lightweight);
    updateLivePositions();
    updateLineStopMarks();
    refreshPointMarks();
    viewportHooks.forEach(cb=>{try{cb(lightweight);}catch(error){console.error('[扩展图层]',error);}});
    if(!lightweight){
      railLayer.update();
      extraLayers.forEach(entry=>entry.layer.update());
      // 等高线的"该画到哪一级"由缩放决定（官方 fadeDist）。包 try/catch：
      // 首帧 updateViewport 可能跑在等高线那几个 const 初始化之前（暂时性死区）。
      try{ refreshContoursOnViewChange(); }catch(error){}
    }
    // 高亮层必须压在所有数据图层之上。
    // 叠放顺序完全由 append 顺序决定（越后越上），而数据图层是**异步加载**的，
    // 拖动/缩放时还会继续 append 分块 —— 谁后到谁就把高亮压住。
    // 所以每帧都提一次（轻量版也要跑 —— 分块恰恰是在拖动过程中加载的）。
    // 函数内部自查父子关系，真需要移动时才碰 DOM；首帧可能跑在 lineRouteLayer
    // 初始化之前（const 暂时性死区），用 try/catch 兜住，与上面同一套办法。
    try{ raiseHighlightLayers(); }catch(error){}
    syncPixiViewport();
    // 与 SVG 同帧出图（autoStart 已关）。放最后，保证用的是本帧最新的 pan/zoom。
    if(pixiApp)pixiApp.render();
  };
  let panFrame=0;
  // 拖动中只跑轻量版；松手时 stopDrag 会补一次完整的。
  const schedulePanRender=()=>{if(!panFrame)panFrame=requestAnimationFrame(()=>{panFrame=0;updateViewport(true);});};
  const setZoom=(value,focusX=600,focusY=360)=>{const next=Math.max(1,Math.min(256,value)),ratio=next/zoom,offsetX=focusX-600,offsetY=focusY-360;panX=offsetX-(offsetX-panX)*ratio;panY=offsetY-(offsetY-panY)*ratio;zoom=next;updateViewport();};
  // 朝向：改角度要让整张图按新朝向重绘，所以写进 URL 后重新加载页面。
  // 入口 = ±90° 按钮 + 直接输入度数（回车应用）。
  const headingValue=((Math.round(mapHeading)%360)+360)%360;
  const applyHeading=next=>{
    const value=((Math.round(next)%360)+360)%360;
    try{localStorage.setItem('railMapHeading',String(value));}catch(error){}
    const url=new URL(location.href);
    if(value===90)url.searchParams.delete('heading');else url.searchParams.set('heading',String(value));
    location.href=url.toString();
  };
  document.querySelector('#zoom-in').onclick=()=>setZoom(zoom*1.6,600,360);
  document.querySelector('#zoom-out').onclick=()=>setZoom(zoom/1.6,600,360);
  // 复位：缩放、平移、朝向一起回初始状态（朝向 = 90°）。朝向不对就重载一次，那次顺带把视野也归零。
  document.querySelector('#zoom-reset').onclick=()=>{
    zoom=1;panX=0;panY=0;
    if(headingValue!==90){applyHeading(90);return;}
    updateViewport();
  };
  const headingInput=document.querySelector('#heading-input');
  if(headingInput){
    headingInput.value=String(headingValue);
    headingInput.addEventListener('keydown',event=>{
      if(event.key!=='Enter')return;
      event.preventDefault();
      const raw=Number(headingInput.value);
      if(!Number.isFinite(raw)){headingInput.value=String(headingValue);return;}
      applyHeading(raw);
    });
  }
  const headingCcw=document.querySelector('#heading-ccw');
  if(headingCcw)headingCcw.onclick=()=>applyHeading(headingValue-90);
  const headingCw=document.querySelector('#heading-cw');
  if(headingCw)headingCw.onclick=()=>applyHeading(headingValue+90);
  // 侧边栏折叠：状态记在 localStorage，收起后地图占满宽度（grid 第三列归零）
  const sidebarToggle=document.querySelector('#sidebar-toggle');
  const workspaceEl=document.querySelector('.workspace');
  if(sidebarToggle&&workspaceEl){
    const storedCollapsed=(()=>{try{return localStorage.getItem('railMapSidebarCollapsed');}catch(error){return null;}})();
    const setCollapsed=collapsed=>{
      workspaceEl.classList.toggle('sidebar-collapsed',collapsed);
      sidebarToggle.textContent=collapsed?'«':'»';
      sidebarToggle.title=collapsed?'展开右侧栏':'收起右侧栏';
      try{localStorage.setItem('railMapSidebarCollapsed',collapsed?'1':'0');}catch(error){}
      updateViewport();
    };
    setCollapsed(storedCollapsed==='1');
    sidebarToggle.onclick=()=>setCollapsed(!workspaceEl.classList.contains('sidebar-collapsed'));
  }
  svg.addEventListener('wheel',event=>{event.preventDefault();const rect=svg.getBoundingClientRect(),focusX=(event.clientX-rect.left)*1200/rect.width,focusY=(event.clientY-rect.top)*720/rect.height;setZoom(zoom*(event.deltaY<0?1.35:1/1.35),focusX,focusY);},{passive:false});
  svg.addEventListener('dragstart',event=>event.preventDefault());
  svg.addEventListener('selectstart',event=>event.preventDefault());
  svg.addEventListener('pointerdown',event=>{if(!event.isPrimary||event.button!==0)return;event.preventDefault();dragging=true;dragPointerId=event.pointerId;lastX=dragStartX=event.clientX;lastY=dragStartY=event.clientY;suppressClick=false;svg.setPointerCapture(event.pointerId);svg.classList.add('dragging');});
  svg.addEventListener('pointermove',event=>{if(!dragging||event.pointerId!==dragPointerId)return;event.preventDefault();if(Math.hypot(event.clientX-dragStartX,event.clientY-dragStartY)>4)suppressClick=true;const rect=svg.getBoundingClientRect();panX+=(event.clientX-lastX)*1200/rect.width;panY+=(event.clientY-lastY)*720/rect.height;lastX=event.clientX;lastY=event.clientY;schedulePanRender();});
  const stopDrag=event=>{if(event&&dragPointerId!==null&&event.pointerId!==dragPointerId)return;const pointerId=dragPointerId;const wasDragging=dragging;dragging=false;dragPointerId=null;svg.classList.remove('dragging');if(pointerId!==null&&svg.hasPointerCapture(pointerId))svg.releasePointerCapture(pointerId);/* 拖动中跑的是轻量版（跳过 tile 装载与标签碰撞检测），松手补一次完整的 */if(wasDragging)updateViewport();};
  svg.addEventListener('pointerup',stopDrag);svg.addEventListener('pointercancel',stopDrag);svg.addEventListener('lostpointercapture',()=>stopDrag());window.addEventListener('blur',()=>stopDrag());
  svg.addEventListener('click',event=>{if(suppressClick){event.preventDefault();event.stopImmediatePropagation();suppressClick=false;}},true);

  renderOverviewSidebar();
  document.querySelector('#station-name').textContent='全路网';
  document.querySelector('#snapshot').textContent=`${p.counts.stations} STATIONS / ${p.counts.lines} LINES`;
  document.querySelector('.mode').textContent='NETWORK CONTROL · DYNAMIC';
  document.querySelector('.watermark').textContent='Powered By BlackIce.';
  document.querySelector('.clock').textContent='STATIC';
  $('#footer-info').text('列车位置刷新时间: 0.5s');
  const $signalToggle=$('#toggle-signals');
  $signalToggle.prop('hidden',false).attr('aria-pressed','true').on('click',()=>{
    signalsVisible=!signalsVisible;
    $signalToggle.attr('aria-pressed',String(signalsVisible)).text(signalsVisible?'隐藏信号机':'显示信号机');
    updateLivePositions();
  });
  const generation=p.generated_at;
  let reloadRequested=false;
  const handleStatus=status=>{
    const mode=document.querySelector('.mode');
    mode.textContent=status.bridge_connected?'NETWORK CONTROL · LIVE':'NETWORK CONTROL · OFFLINE';
    document.querySelector('#snapshot').textContent=`${p.counts.stations} STATIONS / ${p.counts.lines} LINES · SEQ ${status.snapshot_sequence??'—'}`;
    const saveReady=!status.save_transition&&status.save_id&&status.rail_save_id===status.save_id;
    const mapChanged=(status.rail_generation&&String(status.rail_generation)!==String(generation))||(p.save_id&&p.save_id!==status.save_id);
    if(saveReady&&mapChanged&&!reloadRequested){
      reloadRequested=true;
      const target=new URL(location.href),nextGeneration=String(status.rail_generation||'');
      if(target.searchParams.get('_rail')!==nextGeneration){target.searchParams.set('_rail',nextGeneration);location.replace(target.href);}
    }
  };
  window.addEventListener('rail-map-status',event=>handleStatus(event.detail));
  if(window.RAIL_MAP_STATUS)handleStatus(window.RAIL_MAP_STATUS);
  if(location.protocol==='http:'||location.protocol==='https:'){
    let liveRequestPending=false;
    // 轮询调度：**窗口失去焦点时自动降频到 1/6**。
    // 为什么需要：本机 CPU/网络基本都让给 TPF2，而前端在"什么都没动"时仍在每 500 ms 拉
    // /api/live（还有每 2 s 的日志、每 10 s 的建议……）。用户切去玩游戏时，这些纯属白烧。
    // 为什么**不能直接停**：他可能把地图摆在副屏上盯着看，停掉就再也不刷新了。
    // 为什么不用 setInterval：间隔得每拍现判（焦点会来回变），而 setInterval 的周期是起表时定死的。
    const POLL_SLOWDOWN=6;
    const pollShouldSlow=()=>document.hidden||!document.hasFocus();
    const loopPoll=(fn,baseMs)=>{
      const tick=()=>{
        try{fn();}catch(error){console.error(error);}
        setTimeout(tick,pollShouldSlow()?baseMs*POLL_SLOWDOWN:baseMs);
      };
      tick();
    };
    const pollLive=()=>{if(liveRequestPending)return;liveRequestPending=true;fetch('/api/live',{cache:'no-store'}).then(response=>{if(!response.ok)throw new Error(`live: ${response.status}`);return response.json();}).then(reconcileLive).catch(()=>{}).finally(()=>{liveRequestPending=false;});};
    const pollControl=()=>fetch('/api/control',{cache:'no-store'}).then(response=>{if(!response.ok)throw new Error(`control: ${response.status}`);return response.json();}).then(reconcileLive).catch(()=>{});
    let operationsRequestPending=false;
    const pollOperationsContext=()=>{if(operationsRequestPending)return;operationsRequestPending=true;fetch('/api/operations-context',{cache:'no-store'}).then(response=>{if(!response.ok)throw new Error(`operations-context: ${response.status}`);return response.json();}).then(value=>{operationsContext=value;operationLineById.clear();(value.lines||[]).forEach(line=>operationLineById.set(line.line_id,line));if(selectedStation)refreshStationOperationsSidebar();}).catch(error=>console.error(error)).finally(()=>{operationsRequestPending=false;});};
    loopPoll(pollOperationsContext,10000);
    const pollAdvice=()=>Promise.all([
      fetch('/api/ai-suggestions',{cache:'no-store'}).then(response=>{if(!response.ok)throw new Error(`ai-suggestions: ${response.status}`);return response.json();}),
      fetch('/api/mcp-work-log?limit=30',{cache:'no-store'}).then(response=>{if(!response.ok)throw new Error(`mcp-work-log: ${response.status}`);return response.json();})
    ]).then(([advice,work])=>{if(aiAdviceGeneration!==advice.generated_at){aiAdviceVisibleCount=10;aiAdviceGeneration=advice.generated_at;}aiAdvice=advice;mcpWorkLog=work;
      // 概览侧栏只显示线路表、运行图建议与调整记录，三者变化都很慢：
      // 内容没变就不重建，避免每 10 秒整块 replaceChildren 造成的闪屏。
      const key=`${advice.generated_at||''}|${aiAdviceVisibleCount}|${(work.entries||[]).length}|${(advice.suggestions||[]).length}`;
      if(!selectedStation&&selectedVehicleId==null&&key!==overviewKey){overviewKey=key;renderOverviewSidebar();}
    }).catch(error=>console.error(error));
    loopPoll(pollAdvice,10000);
    // loopPoll 自带首次调用 —— 不用再像原来那样先手动调一次、否则会立刻重复请求一次。
    loopPoll(pollLive,500);loopPoll(pollControl,30000);loopPoll(loadStationLogs,2000);
  }
  // ===== 线路路径高亮：沿实际轨道覆盖一层颜色（像游戏里选中线路那样）===========
  // 数据源 `rail-network-data.json`（6.4 MB，含 9765 条边 + 9667 个节点的完整几何）。
  //   **按需加载** —— 首屏绝不碰它，只有真的要画某条线时才 fetch，之后缓存在内存 + 浏览器缓存。
  //   为什么不用 manifest：manifest 的 lines 只有 `stops` / `overview_segments`，
  //   **没有 `route_edge_ids`** —— 而那是"按顺序的边 ID 列表"，是重建真实走行路径的唯一依据。
  // 画法：逐边复用 `edgePath` 拼成一条 path。**不需要处理方向与接续** ——
  //   每条边自己就是从 node0 到 node1 的一段贝塞尔曲线，相邻边共享端点，首尾自然接上。
  //   （实测 30/36 条线有 route_edge_ids，相邻边首尾相接 4215 处 / 断开 70 处，
  //    断开处本来就是各自独立的子路径，不连反而对。）
  const lineRouteLayer=S('g',{id:'network-line-route-layer','pointer-events':'none'},'',mapLayer);
  // 用户 2026-09-29：青色在深色底上"看不清"，改红。**内层亮线保持这个色**，不再动。
  const LINE_HIGHLIGHT_COLOR='#ff3b30';
  // 把所有"高亮"性质的容器提到各自父节点的**末尾**（= 最上层）。
  // ⚠️ 两套坐标系要分开提：lineRouteLayer 是世界坐标（挂在 mapLayer 里），
  //    lineStopLayer 是屏幕坐标（挂在 svg 根层，见 S() 的默认 parent）。
  //    以后加"产业链流向线"时，只要它的挂载点也写进这里，就自动在最顶层。
  // 用户 2026-09-30 要求：「流向线要在最顶层，所有高亮线都应该在顶层，
  //    但是允许高亮线直接覆盖」—— 所以这里不做任何避让，只保证层级。
  // appendChild 对已存在的元素是**移动**语义，不产生副本；移动前先比 lastElementChild，
  // 不需要动的时候一次 DOM 操作都不做（拖动中每帧都会调到）。
  const raiseHighlightLayers=()=>{
    if(lineRouteLayer.parentNode===mapLayer&&mapLayer.lastElementChild!==lineRouteLayer){
      mapLayer.appendChild(lineRouteLayer);
    }
    const stopsParent=lineStopLayer.parentNode;
    if(stopsParent&&stopsParent.lastElementChild!==lineStopLayer){
      stopsParent.appendChild(lineStopLayer);
    }
  };

  // 线路的**真实颜色**：来自游戏本体（官方通用组件 `Color`「Specifies the color of an entity」，
  // 字段 `color: Vec3f`；`Line` 类自己也带 `color`），由 collectors/layer_lines.lua 采出来。
  // 采不到（老数据 / mod 没给）就返回 null，调用方自己兜底 —— 不猜颜色。
  const lineColorOf=line=>{
    const c=line&&line.color;
    if(!c||typeof c.r!=='number'||typeof c.g!=='number'||typeof c.b!=='number')return null;
    const to=v=>Math.round(Math.max(0,Math.min(1,v))*255);
    return `rgb(${to(c.r)} ${to(c.g)} ${to(c.b)})`;
  };
  // 光晕专用：游戏里的线色常常很暗（例如官方调色板第一档 rgb(94,47,0)），
  // 直接拿它当光晕，在深底上等于没画。所以**保色相、抬亮度**——最多提到峰值 1.0、最多提 2.6 倍。
  // 这样"看着就是那条线的颜色"，而内层那条亮线保证任何底色/缩放下都看得清。
  const lineGlowColor=line=>{
    const c=line&&line.color;
    if(!c||typeof c.r!=='number')return LINE_HIGHLIGHT_COLOR;
    const peak=Math.max(c.r,c.g,c.b)||1;
    const lift=Math.min(1/peak,2.6);
    const to=v=>Math.round(Math.min(1,Math.max(0,v)*lift)*255);
    return `rgb(${to(c.r)} ${to(c.g)} ${to(c.b)})`;
  };
  // 缺口补偿的直线：超过这个长度就不补（明显穿墙，宁缺勿错）。
  const LINE_GAP_MAX_METERS=3000;
  let lineRouteData=null,lineRouteRequest=null,highlightedLineId=null;

  const ensureLineRouteData=()=>{
    if(lineRouteData)return Promise.resolve(lineRouteData);
    if(!lineRouteRequest){
      lineRouteRequest=fetch('/rail-network-data.json')
        .then(response=>response.ok?response.json():null)
        .then(data=>{lineRouteData=data;return data;})
        .catch(error=>{console.error('[map] 线路路径数据加载失败',error);return null;});
    }
    return lineRouteRequest;
  };
  const lineOf=id=>(p.lines||[]).find(line=>Number(line.entity_id)===Number(id))||null;
  // 这条线停靠哪些站：manifest 的 stops 只给 `station_group_id`，要回 stations 里查名字。
  const lineStopsOf=id=>{
    const line=lineOf(id);
    if(!line)return [];
    return (line.stops||[])
      .map(stop=>({stop,station:p.stations.find(item=>Number(item.entity_id)===Number(stop.station_group_id))||null}))
      .filter(item=>item.station)
      .sort((a,b)=>(a.stop.sequence_index||0)-(b.stop.sequence_index||0));
  };
  const renderLineSidebar=()=>{
    const line=highlightedLineId!=null?lineOf(highlightedLineId):null;
    if(!line){renderOverviewSidebar();return;}
    setSidebarBackVisible(true);
    const stops=lineStopsOf(line.entity_id);
    const edgeIds=((lineRouteData&&lineRouteData.lines)||[]).find(item=>Number(item.entity_id)===Number(line.entity_id));
    const hasRoute=Boolean(edgeIds&&(edgeIds.route_edge_ids||[]).length);
    const sidebar=document.createElement('div');
    sidebar.className='station-sidebar line-sidebar';
    const add=(tag,cls,text)=>{const el=document.createElement(tag);if(cls)el.className=cls;if(text!=null)el.textContent=text;sidebar.appendChild(el);return el;};
    const title=add('h3',null,null);
    // 标题前放一个游戏里的真实线色块 —— 和游戏内线路表一致，一眼认得出是哪条线。
    const swatch=lineColorOf(line);
    if(swatch){
      const dot=document.createElement('i');
      dot.className='line-swatch line-swatch-lg';
      dot.style.background=swatch;
      title.appendChild(dot);
    }
    title.appendChild(document.createTextNode(line.name||`线路 ${line.entity_id}`));
    const parts=[];
    if(lineGapInfo.count)parts.push(`补缺口 ${lineGapInfo.count} 段`);
    if(lineGapInfo.skipped)parts.push(`${lineGapInfo.skipped} 段过长未补`);
    if(lineGapInfo.ring)parts.push(`环线收口 ${lineGapInfo.ring} 段（合并接缝后找到的另一半）`);
    const gapNote=parts.length?(` · `+parts.join(' · ')):'';
    add('div','event',`经过 ${stops.length} 站 · 路径数据 ${hasRoute?'可用':'缺失（这条线没有 route_edge_ids）'}`
      +(lineRouteData?'':' · 首次点击时加载')+gapNote);
    add('div','panel-title','沿线停靠（点站名跳到该站）');
    const list=add('div','line-stop-list');
    if(!stops.length)list.appendChild(templates.message('UNKNOWN','这条线没有停靠站记录',true));
    stops.forEach((item,index)=>{
      const row=document.createElement('button');
      row.type='button';
      row.className='line-stop-row';
      row.textContent=`${index+1}. ${item.station.name}`;
      row.addEventListener('click',()=>{
        selectedStation=item.station;selectedVehicleId=null;
        const q=P(item.station.center);
        zoom=Math.min(256,Math.max(zoom,scaleBarPixels/baseScale/25));
        panX=-(q.x-600)*zoom;panY=-(q.y-360)*zoom;
        clearLineHighlight();updateViewport();renderStationSidebar();loadStationLogs();
      });
      list.appendChild(row);
    });
    const clear=add('button','line-stop-row','清除线路高亮');
    clear.addEventListener('click',()=>{clearLineHighlight();updateViewport();});
    document.querySelector('#sidebar').replaceChildren(sidebar);
    document.querySelector('#station-name').textContent=line.name||`线路 ${line.entity_id}`;
  };
  const clearLineHighlight=()=>{
    highlightedLineId=null;
    lineGapInfo={count:0,skipped:0};
    lineRouteLayer.replaceChildren();
    lineStopLayer.replaceChildren();
    lineStopMarks=[];
  };
  const highlightLine=async lineId=>{
    const wanted=Number(lineId);
    if(!Number.isFinite(wanted)){clearLineHighlight();renderOverviewSidebar();return null;}
    highlightedLineId=wanted;
    renderLineSidebar();                        // 先用 manifest 的信息出面板，不等那 6 MB
    const data=await ensureLineRouteData();
    if(highlightedLineId!==wanted)return null;  // 这期间用户又选了别的线
    lineRouteLayer.replaceChildren();
    lineStopLayer.replaceChildren();
    lineStopMarks=[];
    if(!data){renderLineSidebar();return null;}
    const source=(data.lines||[]).find(item=>Number(item.entity_id)===wanted);
    const edgeIds=(source&&source.route_edge_ids)||[];
    if(!edgeIds.length){renderLineSidebar();return null;}
    const edgeById=new Map((data.edges||[]).map(edge=>[Number(edge.entity_id),edge]));
    const nodeById=new Map((data.nodes||[]).map(node=>[Number(node.entity_id),node.position]));
    let d='',drawn=0;
    edgeIds.forEach(id=>{
      const edge=edgeById.get(Number(id));
      if(!edge)return;
      if(!nodeById.get(Number(edge.node0))||!nodeById.get(Number(edge.node1)))return;
      d+=edgePath(edge,nodeById);drawn++;
    });
    // 断连缺口补偿：导出时因**图不连通**算不出路径，`routing.disconnected_segments`
    // 记下了这些"本该连上却算不出"的段（本存档共 11 段，例如
    // 津京空轨外环 北京(428174)→前北京(411748) 422 m、天津中央车站→天津中央车站 564 m）。
    // 不补的话环线的端头就是断的 —— 用户 2026-09-29 报的"环线没识别出来"正是这个。
    // 只补**直线距离 ≤ 3 km** 的（更长的直线会明显穿墙，宁缺勿错）。
    let gapCount=0,gapSkipped=0;
    ((p.routing&&p.routing.disconnected_segments)||[]).forEach(seg=>{
      if(Number(seg.line_id)!==wanted)return;
      const a=nodeById.get(Number(seg.from)),b=nodeById.get(Number(seg.to));
      if(!a||!b){gapSkipped++;return;}
      if(Math.hypot(a.x-b.x,a.y-b.y)>LINE_GAP_MAX_METERS){gapSkipped++;return;}
      const pa=P(a),pb=P(b);
      d+=`M${pa.x.toFixed(1)},${pa.y.toFixed(1)}L${pb.x.toFixed(1)},${pb.y.toFixed(1)}`;
      gapCount++;
    });
    lineGapInfo={count:gapCount,skipped:gapSkipped,ring:0};
    // 环线收口（用户约定：环线命名为「xx环线」）：TPF2 的轨道接缝是**同一坐标的两个节点**
    // （实测环线两端各相距 5 m），按 node id 建图会把一条连通的环切成两棵独立的树 ——
    // 这就是"环线看着不闭合 / 像被盖住了"的根因。rail-graph.js 先合并 ≤10 m 的近邻节点，
    // 再找"**没画过的**另一半"（实测 4 条环线都能找到，且与主路径 0 重叠）。
    // ⚠️ 名字要从 manifest 现查（`lineOf`）—— 这里的入参是 `lineId`，
    //    之前误写成 `line.name`，`line` 根本不存在 → ReferenceError，
    //    而且是抛在 `if(d)` **之前**，导致**整条线的高亮全部画不出来**（2026-09-29 浏览器实测发现）。
    const manifestLine=lineOf(wanted);
    if(/环/.test((manifestLine&&manifestLine.name)||'')&&window.RailGraph){
      const closure=window.RailGraph.findRingClosure(lineRouteData,edgeIds);
      closure.forEach(id=>{const edge=edgeById.get(Number(id));if(edge)d+=edgePath(edge,nodeById);});
      lineGapInfo.ring=closure.length;
    }
    if(d){
      // 两层：外层光晕（宽、半透明）做出"覆盖"的观感，内层亮线保证任何缩放下都看得见。
      // 光晕用**游戏里这条线的真实颜色**（抬过亮度，见 lineGlowColor）；采不到就退回红色。
      S('path',{d,fill:'none',stroke:lineGlowColor(manifestLine),'stroke-width':7,opacity:.32,
        'stroke-linecap':'round','stroke-linejoin':'round','vector-effect':'non-scaling-stroke','pointer-events':'none'},'',lineRouteLayer);
      S('path',{d,fill:'none',stroke:'#eaf9ff','stroke-width':1.8,opacity:.95,
        'stroke-linecap':'round','stroke-linejoin':'round','vector-effect':'non-scaling-stroke','pointer-events':'none'},'',lineRouteLayer);
    }
    // 站点标记做成**游戏里那种"编号方块 + 站名"**（用户 2026-09-29 给的截图就是这样式：
    // 橙色方块写着停靠顺序，旁边跟站名）。编号与 stops 顺序一致，和运行图/游戏对得上。
    lineStopsOf(wanted).forEach((item,index)=>{
      const group=S('g',{transform:'translate(-999 -999)','pointer-events':'none'},'',lineStopLayer);
      S('rect',{x:-9,y:-9,width:18,height:18,rx:3,fill:LINE_HIGHLIGHT_COLOR,
        stroke:'#3d0b07','stroke-width':1.3},'',group);
      // ⚠️ 本文件的 S() 签名是 (tag, attrs, text, **parent=DOM 节点**) —— 第 4 个参数就是父节点，
      //    不是 app.js 那套 jQuery 版。多塞一个 `''` 会把父节点变成字符串 →
      //    "parent.appendChild is not a function"（2026-09-29 浏览器实测发现）。
      S('text',{x:0,y:4.5,'text-anchor':'middle',fill:'#fff','font-size':11,'font-weight':'bold',
        'font-family':'Consolas'},String(index+1),group);
      S('text',{x:13,y:4.5,fill:'#ffe6e2','font-size':9,
        'font-family':'Consolas, Microsoft YaHei','paint-order':'stroke',stroke:'#100405','stroke-width':2.6,
        'stroke-linejoin':'round'},item.station.name,group);
      lineStopMarks.push({group,position:item.station.center});
    });
    updateLineStopMarks();
    console.log(`[map] 线路高亮 ${wanted}：${drawn} 条边 / ${lineStopMarks.length} 站`);
    renderLineSidebar();
    return {edges:drawn,stops:lineStopMarks.length};
  };

  const requestedStationId=Number(new URLSearchParams(window.location.search).get('station'));
  const requestedStation=p.stations.find(station=>station.entity_id===requestedStationId);
  if(requestedStation){selectedStation=requestedStation;const q=P(requestedStation.center);zoom=Math.min(256,Math.max(zoom,scaleBarPixels/baseScale/25));panX=-(q.x-600)*zoom;panY=-(q.y-360)*zoom;renderStationSidebar();loadStationLogs();}
  // ?line=<id>：从运行图/别处跳进来时直接高亮这条线路（**异步**，路径数据 6.4 MB 按需加载）。
  const requestedLineId=Number(new URLSearchParams(window.location.search).get('line'));
  if(Number.isFinite(requestedLineId)&&requestedLineId>0)highlightLine(requestedLineId);
  updateViewport();

  // ===== 地形层：等高线 + 水深 + 地下设施 ==============================
  // 这层跟其他图层不是一类东西：公路/产业/车辆是"细节"（分块、放大才加载），
  // 地形是"底图"（整图一个网格、始终显示）。所以它走独立路径：
  //   * 不分块 —— 等高线按 tile 切开就断了，而整张网格才几十 KB
  //   * 只画一次 —— mapLayer 用 SVG transform 负责缩放平移，里面的元素不必重画
  // 数据源：mod 用 game.interface.getHeight({x, y}) 采样的地表高度网格。
  // 单位米、海平面 = 0：> 0 是陆地（画等高线），< 0 是水下（水深 = -height）。
  // 同一份采样同时喂两个开关，不需要采两遍。
  // 官方四级等高线：base_config.gui.layers.contourLines（res/config/base_config.lua:209–222）。
  //   majorContour        100 m / 线宽 1.5 / fadeDist −1（-1 = 一直画）
  //   minorContour         50 m / 线宽 0.75 / −1
  //   intermediateContour  10 m / 线宽 0.75 / 4000
  //   detailContour         2 m / 线宽 0.75 / 500    （官方 alpha 再乘 0.3）
  // ⚠️ 官方那套颜色是"浅底上的深线"（近黑 + alpha .5，细节级 .15）——本图是**深底**，
  //    照抄等于不画。所以这里只搬**结构**（级别 / 线宽 / 淡出距离 / 主次透明秩序），
  //    颜色沿用本图按高度渐变的那套（青→褐），alpha 等比抬到 .95/.75/.55/.30 保住秩序。
  const CONTOUR_SPEC = [
    { level: 100, width: 1.5,  alpha: 0.95, fadeDist: -1 },
    { level: 50,  width: 0.75, alpha: 0.75, fadeDist: -1 },
    { level: 10,  width: 0.75, alpha: 0.55, fadeDist: 4000 },
    { level: 2,   width: 0.75, alpha: 0.30, fadeDist: 500 },
  ];
  const TERRAIN = {
    grid: null, heights: null,
    contourGroup: null, waterGroup: null, undergroundGroup: null,
    contourCache: null, contourCacheKey: null, contourInterval: 50,
    undergroundCount: null,
    visibleContours: true, visibleWater: true, visibleUnderground: true,
  };

  // 任意点的地表高度（双线性插值）。地下车站的判定就靠它：站台 z 与这里得到的
  // 地表高度一比，差值就是"埋多深"。地形网格没覆盖到的地方返回 null。
  const terrainHeightAt = (x, y) => {
    const g = TERRAIN.grid, heights = TERRAIN.heights;
    if (!g || !heights || !g.step_x || !g.step_y) return null;
    const fx = (x - g.origin.x) / g.step_x, fy = (y - g.origin.y) / g.step_y;
    if (fx < 0 || fy < 0 || fx > g.cols - 1 || fy > g.rows - 1) return null;
    const i = Math.min(Math.floor(fx), g.cols - 2), j = Math.min(Math.floor(fy), g.rows - 2);
    const tx = fx - i, ty = fy - j, missing = g.missing, scale = g.scale || 1;
    const at = (ii, jj) => { const v = heights[jj * g.cols + ii]; return (v === missing || v == null) ? NaN : v / scale; };
    const a = at(i, j), b = at(i + 1, j), c = at(i + 1, j + 1), d = at(i, j + 1);
    if ([a, b, c, d].some(Number.isNaN)) return null;
    return (a * (1 - tx) + b * tx) * (1 - ty) + (d * (1 - tx) + c * tx) * ty;
  };

  // Marching squares：从高度网格里抽出等值线。算法在 terrain-contour.js —— 纯函数、不含 DOM，
  // Node 里能直接跑它验几何，所以不必靠"打开页面看一眼"来判断等高线算得对不对。
  //
  // 这一层按**官方四级**做（见 CONTOUR_SPEC），并落实官方的 fadeDist：
  //   · 100 / 50 m 无 fadeDist ⇒ 永远算；
  //   · 10 m 只在视口跨度 ≤ 4000 m 时算；2 m 只在 ≤ 500 m 时算。
  //   · 细则档**按视口裁窗**：整图 2 m 实测 21.4 万段 / 411 ms / 路径串约 4 MB，
  //     整图铺出来会卡死（本项目已经栽过一次：4.6 万格逐格 SVG = 2.6 MB 路径串）。

  // 当前可视范围的世界跨度（米）。baseScale 把世界换成底图坐标，zoom 再把底图换成屏幕，
  // 所以 1200 px 宽的视口对应 1200/(baseScale*zoom) 米。
  const visibleSpanMeters = () => (baseScale > 0 ? 1200 / (baseScale * zoom) : Infinity);

  // 官方 fadeDist 的等价物：跨度越小，才允许放越细的一级。下限 50 —— 100/50 永不淡出。
  const contourIntervalFor = span => (span <= 500 ? 2 : span <= 4000 ? 10 : 50);

  // 细则档的视口窗口。四周留 50% 余量、再乘 √2 抵消地图旋转，下标吸附到 8 格 ——
  // 吸附是为了平移时大部分帧窗口不变，不必重建（重建 10 m 档约 110 ms）。
  const contourWindowFor = interval => {
    const g = TERRAIN.grid;
    if (!g || interval > 10) return null;
    const bx = 600 - panX / zoom, by = 360 - panY / zoom;   // 视口中心在底图坐标里的位置
    const rx = (bx - originX) / baseScale, ry = (originY - by) / baseScale;
    const centre = rotInv(rx, ry);                          // 再换回世界坐标
    const half = visibleSpanMeters() * 0.5 * 1.5 * Math.SQRT2;
    const snap = value => Math.round(value / 8) * 8;
    return {
      i0: snap(Math.floor((centre.x - half - g.origin.x) / g.step_x)),
      i1: snap(Math.ceil((centre.x + half - g.origin.x) / g.step_x)) + 8,
      j0: snap(Math.floor((centre.y - half - g.origin.y) / g.step_y)),
      j1: snap(Math.ceil((centre.y + half - g.origin.y) / g.step_y)) + 8,
    };
  };

  const contourCacheKeyFor = (interval, win) =>
    `${interval}|${win ? [win.i0, win.i1, win.j0, win.j1].join(',') : 'all'}`;

  const buildContours = () => {
    if (!TERRAIN.grid || !TERRAIN.heights) return { groups: [], minH: 0, maxH: 0 };
    const interval = contourIntervalFor(visibleSpanMeters());
    const win = contourWindowFor(interval);
    const key = contourCacheKeyFor(interval, win);
    if (TERRAIN.contourCacheKey === key && TERRAIN.contourCache) return TERRAIN.contourCache;
    TERRAIN.contourCache = window.RailTerrainContour.buildContours(
      TERRAIN.grid, TERRAIN.heights, interval, win);
    TERRAIN.contourCacheKey = key;
    TERRAIN.contourInterval = interval;
    return TERRAIN.contourCache;
  };

  // 缩放/平移会改变"该画到哪一级"，但不必每帧重画 —— 只在级别或窗口真的变了才重建。
  const refreshContoursOnViewChange = () => {
    if (!TERRAIN.visibleContours || !TERRAIN.grid) return;
    const interval = contourIntervalFor(visibleSpanMeters());
    const key = contourCacheKeyFor(interval, contourWindowFor(interval));
    if (key === TERRAIN.contourCacheKey) return;
    renderContours();
  };

  // 某条等高线属于官方四级里的哪一级：能整除它的**最大**那个
  // （100 → 主；150 → 次；20 → 中；4 → 细节；不属于任何一级的按最细处理）。
  const contourRankOf = level => {
    for (const spec of CONTOUR_SPEC) if (Math.abs(level % spec.level) < 1e-6) return spec;
    return CONTOUR_SPEC[CONTOUR_SPEC.length - 1];
  };

  const renderContours = () => {
    if (!TERRAIN.contourGroup) return;
    TERRAIN.contourGroup.replaceChildren();
    if (!TERRAIN.visibleContours || !TERRAIN.grid) return;
    const built = buildContours();
    const groups = built.groups || [];
    if (!groups.length) return;
    const lo = built.minH, hi = built.maxH;
    // 高处偏褐、低处偏青，一眼能看出哪儿是山；线宽与透明度按官方四级给。
    const group = TERRAIN.contourGroup;
    for (const item of groups) {
      // 0 m 是海岸线，归海陆底色层（它更醒目，且和"哪里有水"该同开同关）
      if (Math.abs(item.level) < 1e-9) continue;
      const t = hi > lo ? (item.level - lo) / (hi - lo) : 0;
      const hue = 186 - t * 150;          // 186° 青 → 36° 褐
      const light = 58 - t * 14;
      const spec = contourRankOf(item.level);
      const d = item.segments.map(seg => {
        const p0 = P({ x: seg[0][0], y: seg[0][1] }), p1 = P({ x: seg[1][0], y: seg[1][1] });
        return `M${p0.x.toFixed(1)},${p0.y.toFixed(1)}L${p1.x.toFixed(1)},${p1.y.toFixed(1)}`;
      }).join('');
      S('path', {
        d, fill: 'none', stroke: `hsl(${hue.toFixed(0)} 34% ${light.toFixed(0)}%)`,
        'stroke-width': spec.width, 'vector-effect': 'non-scaling-stroke',
        opacity: spec.alpha, 'pointer-events': 'none',
      }, '', group);
    }
  };

  // 海陆底色。这是这张图最该先做对的一层：存档 2 有 **60.5% 是水**（水深 0 ~ −62 m 的浅海），
  // 而原来只给水下填了三档暗蓝、**陆地完全不填** —— 陆地就剩画布背景（近黑），
  // 于是两边都是暗色，用户原话「我都要把海洋看成陆地了」。
  //
  // 参照真实地图的做法（海图的 bathymetry / 地形图的 hypsometric tint，Google Maps 与 OSM 同理）：
  //   · **水陆两侧都设色**，不是只画水；漏掉任何一侧都等于把那一侧交给背景色。
  //   · **色相拉开**才是关键：水走蓝、陆走中性灰。同色系只差明度，缩远了照样分不清。
  //   · 各自再分档（浅海亮 → 深海暗；低地暗 → 高地亮），让底图有层次、像地图而不是色块。
  //   · 都保持半透明：铁路是 Pixi canvas、在 SVG **底下**，填实了会把它盖住。
  //
  // 另外把 0 m 等值线（海岸线）单独画成一条亮线 —— 真实海图上这条线最醒目，
  // 也是"这里开始没有水"最直接的判据。它和底色同开同关，所以放在这一层。
  const renderWater = () => {
    if (!TERRAIN.waterGroup) return;
    TERRAIN.waterGroup.replaceChildren();
    if (!TERRAIN.visibleWater || !TERRAIN.grid) return;
    const g = TERRAIN.grid, heights = TERRAIN.heights;
    const { cols, rows, step_x, step_y } = g;
    const scale = g.scale || 1, missing = g.missing;
    const ox = g.origin.x, oy = g.origin.y;
    const at = (i, j) => { const v = heights[j * cols + i]; return (v === missing || v == null) ? NaN : v / scale; };

    // 🔴 用 canvas 位图，**不要**逐格画 SVG 四边形。
    //    4.6 万个格子的 path 字符串实测约 2.6 MB，而且它挂在 mapLayer 里 ——
    //    每次平移/缩放浏览器都要重新解析并重绘这几千万个坐标，直接卡死。
    //    画成 cols×rows 的位图后，渲染端只剩一个 <image>，缩放插值交给 GPU。
    const canvas = document.createElement('canvas');
    canvas.width = cols; canvas.height = rows;
    const context = canvas.getContext('2d');
    const pixels = context.createImageData(cols, rows);
    const data = pixels.data;
    // 同一套配色，但**把不透明度直接烘进像素的 alpha**（省一层 SVG compositing）：
    // 铁路是 Pixi canvas、在 SVG 底下，所以底色必须半透明，否则会把铁路盖住。
    const waterBands = [[92, 192, 230], [61, 149, 192], [42, 112, 153], [27, 81, 117]];
    const landBands = [[29, 35, 41], [39, 47, 55], [50, 59, 69], [63, 74, 86]];
    const WATER_ALPHA = 153, LAND_ALPHA = 184;   // 0.60 / 0.72
    for (let j = 0; j < rows; j++) {
      for (let i = 0; i < cols; i++) {
        const value = at(i, j);
        const offset = (j * cols + i) * 4;
        if (Number.isNaN(value)) { data[offset + 3] = 0; continue; }
        let rgb, alpha;
        if (value < 0) {
          rgb = waterBands[value < -40 ? 3 : value < -20 ? 2 : value < -5 ? 1 : 0];
          alpha = WATER_ALPHA;
        } else {
          rgb = landBands[value > 150 ? 3 : value > 60 ? 2 : value > 20 ? 1 : 0];
          alpha = LAND_ALPHA;
        }
        data[offset] = rgb[0]; data[offset + 1] = rgb[1]; data[offset + 2] = rgb[2]; data[offset + 3] = alpha;
      }
    }
    context.putImageData(pixels, 0, 0);

    // 位图坐标 → 底图坐标 的矩阵：像素 (i,j) 代表格点 (i,j)，所以左上角在世界
    // (ox−step_x/2, oy−step_y/2)，x 向右 = +step_x、y 向下（图像行）= +step_y。
    const corner = P({ x: ox - step_x / 2, y: oy - step_y / 2 });
    const stepRight = P({ x: ox + step_x / 2, y: oy - step_y / 2 });
    const stepDown = P({ x: ox - step_x / 2, y: oy + step_y / 2 });
    const m = [stepRight.x - corner.x, stepRight.y - corner.y,
               stepDown.x - corner.x, stepDown.y - corner.y, corner.x, corner.y];
    S('image', {
      href: canvas.toDataURL('image/png'),
      width: cols, height: rows, preserveAspectRatio: 'none', 'pointer-events': 'none',
      transform: `matrix(${m[0].toFixed(5)} ${m[1].toFixed(5)} ${m[2].toFixed(5)} ${m[3].toFixed(5)} ${m[4].toFixed(2)} ${m[5].toFixed(2)})`,
    }, '', TERRAIN.waterGroup);

    // 海岸线（0 m 等值线）仍走矢量：4907 段约 300 KB，比底色小一个数量级，
    // 而且它是要"锐"的线条，位图化反而糊。
    const coast = (buildContours().groups || []).find(item => Math.abs(item.level) < 1e-9);
    if (coast && coast.segments.length) {
      const d = coast.segments.map(seg => {
        const p0 = P({ x: seg[0][0], y: seg[0][1] }), p1 = P({ x: seg[1][0], y: seg[1][1] });
        return `M${p0.x.toFixed(1)},${p0.y.toFixed(1)}L${p1.x.toFixed(1)},${p1.y.toFixed(1)}`;
      }).join('');
      S('path', { d, fill: 'none', stroke: '#8fdcf5', 'stroke-width': 1.4, 'vector-effect': 'non-scaling-stroke',
        opacity: 0.85, 'pointer-events': 'none' }, '', TERRAIN.waterGroup);
    }
  };

  // 地下设施：埋深来自采集器在站点上**直接采样**的 surface_z（存成 depth_m）。
  // 🔴 不再回退到"用地形网格插值算地表高度"：那张网格 170 m 一格，落在山谷里的站
  // 会被相邻格点的山坡拉高，实测把 24 个普通站误标成"地下 3~17 m"（用户报过：
  // 这个存档一个地下站都没有，唯一那个在另一个存档的 Hanoï）。
  // 拿不到 depth_m 就**不标** —— 宁可漏报，也不要再报一堆假的。
  const renderUnderground = () => {
    if (!TERRAIN.undergroundGroup) return;
    TERRAIN.undergroundGroup.replaceChildren();
    if (!TERRAIN.visibleUnderground) return;
    const found = [];
    (p.stations || []).forEach(station => {
      const center = station.center;
      if (!center || typeof center.z !== 'number') return;
      const depth = station.depth_m;
      if (typeof depth !== 'number' || !Number.isFinite(depth) || depth < 3) return;
      // 光"比地表低"还不够 —— 得区分两类：
      //   * 下凹式地面站：站台只是沉在凹地里，上方是空的、或者只有很高的桥 → 不是地下站
      //   * 真地下站：上面盖着**贴地**的道路/建筑 → 才是
      // 采集器已经在 station.overhead 里标好（只认地面类型的公路，桥和隧道不算）。
      if (station.overhead !== 'road') return;
      found.push({ station, depth });
    });
    TERRAIN.undergroundCount = found.length;
    found.forEach(({ station, depth }) => {
      const q = P(station.center);
      S('path', {
        d: `M${(q.x - 4).toFixed(1)},${(q.y - 5).toFixed(1)}L${(q.x + 4).toFixed(1)},${(q.y - 5).toFixed(1)}L${q.x.toFixed(1)},${(q.y + 3).toFixed(1)}Z`,
        fill: '#6c5aa8', stroke: '#ded4ff', 'stroke-width': 0.8, 'pointer-events': 'none',
      }, '', TERRAIN.undergroundGroup);
      S('text', {
        x: (q.x + 6).toFixed(1), y: (q.y - 3).toFixed(1), fill: '#d5c9ff', 'font-size': 7,
        'font-family': 'Consolas, Microsoft YaHei', 'paint-order': 'stroke',
        stroke: '#0b1020', 'stroke-width': 2.2, 'pointer-events': 'none',
      }, `地下 ${depth.toFixed(0)}m`, TERRAIN.undergroundGroup);
    });
  };

  const renderTerrain = () => { renderContours(); renderWater(); renderUnderground(); };

  // 地形容器插到最底：水 → 等高线 → （地下标记在最上，因为它是标注）
  (() => {
    TERRAIN.contourGroup = S('g', { id: 'network-terrain-contour-layer', 'pointer-events': 'none' });
    TERRAIN.waterGroup = S('g', { id: 'network-terrain-water-layer', 'pointer-events': 'none' });
    TERRAIN.undergroundGroup = S('g', { id: 'network-terrain-underground-layer', 'pointer-events': 'none' });
    // insertBefore(firstChild) 每调用一次都把元素放到更下层，所以先插等高线、再插水深
    mapLayer.insertBefore(TERRAIN.contourGroup, mapLayer.firstChild);
    mapLayer.insertBefore(TERRAIN.waterGroup, mapLayer.firstChild);
    mapLayer.appendChild(TERRAIN.undergroundGroup);
  })();

  // ===== 新增图层 ======================================================
  // 数据链：mod 自驱写 bridge/layer-<name>.json → export-layer-map.py 切块 →
  // /api/layers/<name>/manifest 与 /api/layers/<name>/tile/<key>。
  // 切块时用的是铁路 manifest 里那份全局 bounds，所以各层叠加不会错位；
  // 分块的加载 / 卸载复用上面的 createTileLayer，与铁路同一套逻辑。
  const LAYER_SPECS=[
    {name:'road',label:'公路',color:'#8d9aa8',width:1.1,z:'bottom',tunnelColor:'#9b8ae0',bridgeColor:'#dcc07e'},
    {name:'industry',label:'产业',color:'#e8890c',z:'top'},
    {name:'vehicles',label:'车辆',z:'top'},
  ];
  const carrierColor=carrier=>({ROAD:'#2b7fd4',RAIL:'#d43b2b',AIR:'#8a4fd4',WATER:'#17a2a2'}[carrier]||'#8a8a8a');
  // 分块里带什么就画什么：边（EDGE_GRAPH，复用铁路的 Hermite 曲线画法）和点（POINT）
  const renderExtraTile=(spec,container,tile)=>{
    const group=S('g',{'data-tile-key':tile.key},'',container);
    const marks=[];   // 本分块登记的"固定屏幕尺寸"图标，卸块时要撤登记
    const nodeById=new Map((tile.nodes||[]).map(node=>[node.entity_id,node.position]));
    // 边按**样式**合并成 path，而不是一条边一个元素。
    // 为什么：一个分块动辄几千条边（公路 9 970 条边切 74 块），而它们只有 3 种样式
    //   （普通/隧道/桥，见 edgeStructureStyle）—— 逐边建元素等于把几千个 <path> 塞进 DOM，
    //   每次平移/缩放都要 CPU 重新栅格化一遍，而游戏正在抢同一个 CPU。
    //   实测（2026-09-30）：放大状态 SVG 元素 7 279 个、其中 path 5 690；合并后每块只剩 ≤3 条。
    // 为什么安全：applyFilters 只作用于 `#network-vehicles-layer [data-carrier]`，不碰这里；
    //   这里的 path 全程 pointer-events:none（没有逐边交互）；
    //   多段 `M…C…` 直接拼接是合法 SVG。
    // ⚠️ 不要为了"好看"给这些 path 加 filter/阴影 —— 那才是真正的性能杀手。
    const buckets=new Map();
    (tile.edges||[]).forEach(edge=>{
      const style=edgeStructureStyle(edge,spec);
      const key=`${style.stroke}|${style['stroke-width']}|${style['stroke-dasharray']||''}|${style.opacity||1}`;
      let bucket=buckets.get(key);
      if(!bucket){bucket={style,parts:[]};buckets.set(key,bucket);}
      bucket.parts.push(edgePath(edge,nodeById));
    });
    buckets.forEach(bucket=>{
      S('path',{d:bucket.parts.join(''),fill:'none','vector-effect':'non-scaling-stroke','pointer-events':'none',...bucket.style},'',group);
    });
    (tile.points||[]).forEach(point=>{
      const q=P(point.position);
      if(spec.name==='vehicles'){
        // r 按**屏幕像素**给（4 px ≈ 列车菱形宽 8 px 的一半），位置仍用底图坐标，
        // 由 addPointMark 的 transform 反缩放保证缩放时大小不变。
        // data-carrier / data-line 是给筛选用的标记。**职能（客货）不在这里算** ——
        // 它要查线路表，而线路数据可能比车辆分块晚到，所以留到 applyFilters 时现查。
        const attrs={r:4,fill:carrierColor(point.carrier),
          stroke:'#0b1218','stroke-width':0.7,'pointer-events':'none',
          'data-carrier':point.carrier||'UNKNOWN'};
        if(point.line!=null)attrs['data-line']=String(point.line);
        const el=S('circle',attrs,'',group);
        addPointMark(el,q.x,q.y);
        marks.push(el);
      }else if(spec.name==='industry'&&point.extent){
        // 产业：按**厂区实际占地**画范围框，而不是一个小方块。
        // extent 是"世界坐标下的尺寸"（米），用 T() 换算成底图尺寸（含地图朝向与 baseScale）。
        // ⚠️ 兼容旧图块：图块是 09-29 切的、还没带 extent 时，自动退回下面那个小方块。
        const size=T(point.extent);
        const w=Math.max(Math.abs(size.x),4),h=Math.max(Math.abs(size.y),4);
        S('rect',{x:(q.x-w/2).toFixed(1),y:(q.y-h/2).toFixed(1),width:w.toFixed(1),height:h.toFixed(1),
          fill:spec.color,'fill-opacity':.22,stroke:spec.color,'stroke-width':1,
          'vector-effect':'non-scaling-stroke','pointer-events':'none'},'',group);
      }else{
        S('rect',{x:(q.x-2.5).toFixed(1),y:(q.y-2.5).toFixed(1),width:5,height:5,fill:spec.color,'pointer-events':'none'},'',group);
      }
    });
    return {group,marks};
  };
  // ===== 图层面板与三维筛选 ==============================================
  // 三个互相独立、可叠加的分类维度：
  //   种类 carrier —— 列车 / 汽车 / 船舶 / 航空器
  //   职能 cargo   —— 客运 / 货运 / 客货混运（判据：这条线停靠的站台有没有货运站台）
  //   线路 line    —— 具体某一条线
  // 车辆点只带 carrier 与所属 line，**职能是查线路表得来的**，所以线路数据比车辆分块
  // 晚到也不影响 —— 筛选时现查（lineMetaOf）。
  //
  // 筛选语义：每个维度一个集合 + 一个 restricted 开关。
  //   restricted=false → 不限制，全部通过（初始状态）
  //   用户动过任何一个勾选 → restricted=true，集合里放"勾选中的值"
  // 这样"全选"只要把 restricted 复位即可 —— 否则 140 条线得一条条勾回来。
  const CARRIER_ORDER=['RAIL','ROAD','WATER','AIR','UNKNOWN'];
  const CARGO_ORDER=['PASSENGER','FREIGHT','MIXED','UNKNOWN'];
  const CARRIER_LABEL={RAIL:'列车',ROAD:'汽车',WATER:'船舶',AIR:'航空器',UNKNOWN:'未分类'};
  const CARGO_LABEL={PASSENGER:'客运',FREIGHT:'货运',MIXED:'客货混运',UNKNOWN:'未分类'};
  const FILTER={carrier:{restricted:false,set:new Set()},
                cargo:{restricted:false,set:new Set()},
                lines:{restricted:false,set:new Set()}};
  const lineMeta=new Map();       // line_id → {carrier,cargo,name}
  const filterBoxes={carrier:new Map(),cargo:new Map(),lines:new Map()};
  // 「种类」这一组的信息，给 syncFilterBoxes 用：本存档实际有哪些种类、以及"全部种类"那个框。
  let kindCarriers=[];
  let kindAllBox=null;

  const lineMetaOf=id=>id==null?null:(lineMeta.get(Number(id))||null);

  // 车辆与线路共用这一套判定：先看种类，再看职能（车辆职能查线路表），最后看具体线路。
  const applyFilters=()=>{
    const passCarrier=v=>{const f=FILTER.carrier;return !f.restricted||f.set.has(v);};
    const passCargo=v=>{const f=FILTER.cargo;return !f.restricted||f.set.has(v);};
    const passLine=v=>{const f=FILTER.lines;return !f.restricted||(v!=null&&f.set.has(Number(v)));};
    document.querySelectorAll('#network-vehicles-layer [data-carrier]').forEach(node=>{
      const meta=lineMetaOf(node.dataset.line);
      const ok=passCarrier(node.dataset.carrier||'UNKNOWN')
        &&passCargo(meta?meta.cargo:'UNKNOWN')&&passLine(node.dataset.line);
      node.style.display=ok?'':'none';
    });
    // ⚠️ 线路折线已不画，所以这里只剩车辆那一轮 —— 但**筛选维度照样作用于车辆**：
    //    车辆点自带 data-carrier，且 passCargo/passLine 会现查 lineMeta（见上面）。

    // 车辆图层整体显隐：种类全不勾 = 整个图层不显示（连分块都不加载）。
    // 这样「种类」那几个框就是**唯一**控制点，不需要额外的"显示车辆"开关。
    // ⚠️ 只在状态真的变了才调 setVisible —— 它内部会 unloadTile → onChanged → 可能绕回这里。
    if(vehiclesLayer){
      const f=FILTER.carrier;
      const want=!f.restricted||f.set.size>0;
      if(vehiclesLayer.isVisible()!==want)vehiclesLayer.setVisible(want);
    }
    // 实时船 / 飞机跟同一套判定走：勾了"船舶"才显示船，勾了"航空器"才显示飞机。
    carrierVisibleFn=passCarrier;
    airViews.forEach(view=>{view.el.style.display=passCarrier('AIR')?'':'none';});
    waterViews.forEach(view=>{view.el.style.display=passCarrier('WATER')?'':'none';});
  };
  const syncFilterBoxes=()=>{
    // ⚠️「无限制」= 全选，不是"全不选"。种类框现在**同时决定图层显隐**，
    // 所以框的状态必须和"实际显示了什么"一致 —— 否则会出现"框全没勾但满屏是车"。
    const cf=FILTER.carrier;
    filterBoxes.carrier.forEach((box,v)=>{box.checked=!cf.restricted||cf.set.has(v);});
    if(kindAllBox)kindAllBox.checked=!cf.restricted||kindCarriers.every(v=>cf.set.has(v));
    filterBoxes.cargo.forEach((box,v)=>{box.checked=!FILTER.cargo.restricted||FILTER.cargo.set.has(v);});
    filterBoxes.lines.forEach((box,v)=>{box.checked=FILTER.lines.set.has(v);});
  };
  // 用户第一次动勾选时，先把"当前实际是全选"这件事补进集合，
  // 否则其余没被显式勾过的项会被当成"没选"而一起消失。
  const toggleFilter=(dim,value,checked,allValues)=>{
    const f=FILTER[dim];
    if(!f.restricted){f.restricted=true;allValues.forEach(v=>f.set.add(v));}
    if(checked)f.set.add(value);else f.set.delete(value);
    applyFilters();
  };
  const onlyFilter=(dim,values)=>{
    const f=FILTER[dim];f.restricted=true;f.set.clear();values.forEach(v=>f.set.add(v));
    syncFilterBoxes();applyFilters();
  };
  const clearFilters=()=>{
    ['carrier','cargo','lines'].forEach(dim=>{FILTER[dim].restricted=false;FILTER[dim].set.clear();});
    syncFilterBoxes();applyFilters();
  };

  // ---- 面板骨架 ----
  const layerPanel=document.querySelector('#layer-panel');
  const addGroup=title=>{
    const box=document.createElement('div');box.className='layer-group';
    const head=document.createElement('div');head.className='layer-group-title';head.textContent=title;
    box.appendChild(head);
    if(layerPanel)layerPanel.appendChild(box);
    return box;
  };
  const addOption=(group,label,options={})=>{
    const{checked=true,onChange,count,title,scroll,swatch}=options;
    const wrap=document.createElement('label');
    if(title)wrap.title=title;
    // 线路色块：游戏里这条线是什么颜色，列表里就显示什么颜色（官方 `Line.color` / `Color` 组件）。
    // 采不到就不画色块 —— 不用自造颜色冒充。
    if(swatch){const dot=document.createElement('i');dot.className='line-swatch';dot.style.background=swatch;wrap.appendChild(dot);}
    const box=document.createElement('input');box.type='checkbox';box.checked=checked;
    box.addEventListener('change',()=>{if(onChange)onChange(box.checked);});
    const text=document.createElement('span');
    text.textContent=count==null?label:`${label} · ${count}`;
    wrap.appendChild(box);wrap.appendChild(text);
    if(group)group.appendChild(wrap);
    if(scroll&&group){group.classList.add('is-scroll');}
    return box;
  };

  const baseGroup=addGroup('底图');
  const netGroup=addGroup('路网与线路');
  const kindGroup=addGroup('交通工具 · 种类');
  const cargoGroup=addGroup('交通工具 · 职能');
  const lineGroup=addGroup('线路（可逐条勾选）');
  const facilityGroup=addGroup('设施');

  const actionBar=document.createElement('div');actionBar.className='layer-actions';
  const addAction=(label,title,fn)=>{
    const button=document.createElement('button');
    button.type='button';button.textContent=label;if(title)button.title=title;
    button.addEventListener('click',fn);
    actionBar.appendChild(button);
  };
  addAction('只看客运','只保留客运与客货混运',()=>onlyFilter('cargo',['PASSENGER','MIXED']));
  addAction('只看货运','只保留货运与客货混运',()=>onlyFilter('cargo',['FREIGHT','MIXED']));
  addAction('只看列车','只保留铁路',()=>onlyFilter('carrier',['RAIL']));
  addAction('还原','取消所有筛选（注意：车辆"种类"会变成全选 = 全部显示）',clearFilters);
  if(layerPanel)layerPanel.appendChild(actionBar);

  // ---- 路网（铁路 / 公路 / 线路）----
  addOption(netGroup,'铁路',{onChange:v=>railLayer.setVisible(v),count:p.tiles.length});

  const createLayerContainer=spec=>{
    const group=S('g',{id:`network-${spec.name}-layer`});
    if(spec.z==='bottom')mapLayer.insertBefore(group,mapLayer.firstChild);
    else mapLayer.appendChild(group);
    return group;
  };

  // ---- 分块图层（公路 / 产业 / 车辆）----
  const layerTasks=[];
  layerTasks.push((async()=>{
    for(const spec of LAYER_SPECS){
      let manifest=null;
      try{
        const response=await fetch(`/api/layers/${spec.name}/manifest`,{cache:'no-store'});
        if(response.ok)manifest=await response.json();
      }catch(error){console.error(error);}
      if(!manifest||!Array.isArray(manifest.tiles)||!manifest.tiles.length)continue;
      const container=createLayerContainer(spec);
      // 概览骨架（总览时显示，放大后被分块取代）—— 与铁路的 physical_overview_segments
      // 同一角色。是静态文件，直接读 /layers/<name>-overview.json，不必再开接口。
      let overview=null;
      const loadOverview=async()=>{
        try{
          const response=await fetch(`/layers/${spec.name}-overview.json`,{cache:'no-store'});
          if(response.ok)overview=await response.json();
        }catch(error){console.error(error);}
      };
      await loadOverview();
      const overviewGroup=S('g',{id:`network-${spec.name}-overview`},'',container);
      let overviewDrawn=false;
      let overviewMarks=[];
      const hideSummary=()=>{overviewGroup.replaceChildren();dropPointMarks(overviewMarks);overviewMarks=[];overviewDrawn=false;};
      // 概览模式下重新拉一次缩略数据并重画（车辆位置会变，概览也得跟着更新）
      const refreshSummary=()=>{hideSummary();loadOverview().then(()=>{showSummary();applyFilters();});};
      const showSummary=()=>{
        if(overviewDrawn||!overview)return;
        overviewDrawn=true;
        if(overview.geometry_kind==='POINT'){
          (overview.points||[]).forEach(entry=>{
            const q=P({x:entry[0],y:entry[1]});
            if(spec.name==='vehicles'){
              // 概览里的车辆同样带标记，筛选才能作用于它们。
              // 同样固定屏幕尺寸，但略小于分块里的 4 px —— 概览时上千个点挤在一起。
              const attrs={r:3,fill:carrierColor(entry[2]),'pointer-events':'none',
                'data-carrier':entry[2]||'UNKNOWN'};
              if(entry[3]!=null)attrs['data-line']=String(entry[3]);
              const el=S('circle',attrs,'',overviewGroup);
              addPointMark(el,q.x,q.y);
              overviewMarks.push(el);
            }else{
              S('rect',{x:(q.x-1.5).toFixed(1),y:(q.y-1.5).toFixed(1),width:3,height:3,fill:spec.color,'pointer-events':'none'},'',overviewGroup);
            }
          });
          return;
        }
        const d=(overview.lines||[]).map(line=>{const a=P({x:line[0],y:line[1]}),b=P({x:line[2],y:line[3]});return `M${a.x.toFixed(1)},${a.y.toFixed(1)}L${b.x.toFixed(1)},${b.y.toFixed(1)}`;}).join('');
        S('path',{d,fill:'none',stroke:spec.color,'stroke-width':.7,'vector-effect':'non-scaling-stroke',opacity:.85,'pointer-events':'none'},'',overviewGroup);
      };
      const layer=createTileLayer({
        name:spec.name,manifest,
        tileUrl:key=>`/api/layers/${spec.name}/tile/${key}`,
        thresholdM:manifest.detail_load_threshold_m||600,
        tileSizeM:manifest.tile_size_m||2000,
        render:tile=>{const entry=renderExtraTile(spec,container,tile);applyFilters();return entry;},
        destroy:entry=>{if(entry.group)entry.group.remove();dropPointMarks(entry.marks);},
        showSummary:()=>{showSummary();applyFilters();},hideSummary,refreshSummary,
      });
      extraLayers.push({spec,layer});
      // 车辆图层**默认不显示**，由「交通工具 · 种类」那几个框统一控制（见下面）：
      // 默认一个都不勾 → 图层不显示、也不加载分块。
      // ⚠️ **不要再单独加"显示车辆"开关** —— 和种类框重复，用户会以为两者冲突
      //    （2026-09-29 用户原话："单独做个显示汽车何意味？"）。
      if(spec.name==='vehicles'){
        vehiclesLayer=layer;
        layer.setVisible(false);
        addOption(cargoGroup,'自动刷新车辆位置',{
          checked:false,
          title:'勾选后每 5 秒回看一次，源数据变了就重载当前视口的分块（源数据约 18 秒一轮）',
          onChange:value=>{vehiclesAutoRefresh=value;},
        });
      }
      layer.update();
      // 加载诊断：打开浏览器控制台就能看到每层采到多少，不必去翻 bridge 文件
      console.log(`[map] 图层 ${spec.name}：${(manifest.counts&&manifest.counts.total)||manifest.tiles.length}`, manifest.by_carrier||manifest.by_cargo||'');

      if(spec.name==='road'){
        addOption(netGroup,'公路',{onChange:v=>layer.setVisible(v),count:manifest.counts&&manifest.counts.total});
      }else if(spec.name==='industry'){
        addOption(facilityGroup,'产业',{onChange:v=>layer.setVisible(v),count:manifest.counts&&manifest.counts.total});
      }else if(spec.name==='vehicles'){
        // 车辆的数量按种类拆开显示，让用户知道每类有多少。
        // ★ 这几个框就是**唯一**的显示控制点：勾哪个种类就显示哪个
        //   （静态点 + 实时船/飞机点一起管），全不勾 = 车辆图层整个不显示，
        //   连分块都不加载 —— 用户 2026-09-29 的要求："勾选哪个就显示哪个"。
        const byCarrier=(manifest.counts&&manifest.counts.total)||0;
        const split=manifest.by_carrier||{};
        const carriers=CARRIER_ORDER.filter(carrier=>split[carrier]!=null);
        kindCarriers=carriers;
        carriers.forEach(carrier=>{
          const box=addOption(kindGroup,CARRIER_LABEL[carrier]||carrier,{
            checked:false,
            count:split[carrier],
            title:'勾了就显示这一类（含实时船/飞机），不勾就隐藏',
            onChange:checked=>toggleFilter('carrier',carrier,checked,carriers),
          });
          filterBoxes.carrier.set(carrier,box);
        });
        kindAllBox=addOption(kindGroup,'全部种类',{
          checked:false,count:byCarrier,
          title:'一键：本组全选 / 全不选（只影响"种类"，不动职能与线路）',
          onChange:checked=>onlyFilter('carrier',checked?carriers:[]),
        });
        onlyFilter('carrier',[]);   // 默认一个都不勾 = 不显示车辆
        CARGO_ORDER.forEach(cargo=>{
          const box=addOption(cargoGroup,CARGO_LABEL[cargo]||cargo,{
            checked:true,
            title:cargo==='UNKNOWN'?'所属线路未采到数据的车辆':'按线路职能筛选',
            onChange:checked=>toggleFilter('cargo',cargo,checked,CARGO_ORDER),
          });
          filterBoxes.cargo.set(cargo,box);
        });
      }
    }
    applyFilters();
  })());

  // ---- 线路图层（整层加载，不分块）----
  layerTasks.push((async()=>{
    let manifest=null;
    try{
      const response=await fetch('/api/layers/lines/manifest',{cache:'no-store'});
      if(response.ok)manifest=await response.json();
    }catch(error){console.error(error);}
    if(!manifest||!manifest.data_file)return;
    let data=null;
    try{
      const response=await fetch(`/layers/${manifest.data_file}`,{cache:'no-store'});
      if(response.ok)data=await response.json();
    }catch(error){console.error(error);}
    if(!data||!Array.isArray(data.lines)||!data.lines.length)return;

    const group=S('g',{id:'network-lines-layer','pointer-events':'none'});
    // 线路画在车辆之下（车辆是点，被线压住会看不清）
    const vehiclesGroup=document.getElementById('network-vehicles-layer');
    if(vehiclesGroup)mapLayer.insertBefore(group,vehiclesGroup);
    else mapLayer.appendChild(group);

    // ⛔ 线路折线**不再画**（用户 2026-09-29 同上）。
    //    原本画的是 `line.points` 的折线 —— 那是**停靠站坐标的直连**，不沿实际轨道路径；
    //    水运/航空更只有起降两个点，就是一根直线。真正的走向看路网图层。
    //    ⚠️ `lineMeta` **必须照旧登记**：车辆点只带 `line` id，而"职能（客/货/混）"
    //    这个维度是靠它现查线路表的（见 applyFilters 的 passCargo）。
    data.lines.forEach(line=>lineMeta.set(Number(line.entity_id),line));

    // 线路逐条勾选：按种类分组，列表可滚动。140 条全列也不会把面板撑爆。
    const linesByCarrier=new Map();
    data.lines.forEach(line=>{
      const key=line.carrier||'UNKNOWN';
      if(!linesByCarrier.has(key))linesByCarrier.set(key,[]);
      linesByCarrier.get(key).push(line);
    });
    const allLineIds=data.lines.map(line=>Number(line.entity_id));
    // 一键全选 / 全不选。140 条线逐条勾太累。
    // 全选直接把这一维复位成"不限制"（restricted=false）—— 比往集合里塞 140 个 id 干净，
    // 效果一样，而且以后新采到的线路也自动算在全选里。
    // 按钮挂在 netGroup 而不是滚动列表里，否则列表一滚按钮就跟着跑掉了。
    const bulkRow=document.createElement('div');
    bulkRow.className='layer-bulk';
    const makeBulk=(label,hint,handler)=>{
      const button=document.createElement('button');
      button.type='button';button.textContent=label;button.title=hint;
      button.onclick=handler;bulkRow.appendChild(button);
    };
    makeBulk('全选','勾上全部线路（等于不限制）',()=>{
      FILTER.lines.restricted=false;FILTER.lines.set.clear();
      filterBoxes.lines.forEach(box=>{box.checked=true;});
      applyFilters();
    });
    makeBulk('全不选','一条线路都不显示',()=>{
      FILTER.lines.restricted=true;FILTER.lines.set.clear();
      filterBoxes.lines.forEach(box=>{box.checked=false;});
      applyFilters();
    });
    netGroup.appendChild(bulkRow);
    CARRIER_ORDER.forEach(carrier=>{
      const groupLines=linesByCarrier.get(carrier);
      if(!groupLines)return;
      const sub=document.createElement('div');sub.className='layer-subgroup';
      const subHead=document.createElement('div');subHead.className='layer-subgroup-title';
      subHead.textContent=`${CARRIER_LABEL[carrier]||carrier} · ${groupLines.length}`;
      sub.appendChild(subHead);
      groupLines.forEach(line=>{
        const box=addOption(sub,line.name||`线路${line.entity_id}`,{
          checked:true,
          swatch:lineColorOf(line),
          title:`种类：${CARRIER_LABEL[line.carrier]||line.carrier}　职能：${CARGO_LABEL[line.cargo]||line.cargo}　车 ${line.vehicle_count||0} 辆`,
          onChange:checked=>toggleFilter('lines',Number(line.entity_id),checked,allLineIds),
        });
        filterBoxes.lines.set(Number(line.entity_id),box);
      });
      lineGroup.appendChild(sub);
    });
    lineGroup.classList.add('is-scroll');
    if(!data.lines.length)addOption(lineGroup,'（没有采到线路）',{checked:false,onChange:()=>{}});
    applyFilters();
    console.log(`[map] 线路图层：${data.lines.length} 条`, '种类', data.by_carrier||{}, '职能', data.by_cargo||{});
  })());

  // 车站互通站群。数据来自 mod 侧 layer_stations.lua：它读引擎的车站辐射表
  // （catchmentAreaSystem.getStation2stationsAndDistancesMap）再用并查集把
  // "连成一片"的车站归成一个 cluster —— 互通是传递的，所以要的连通分量，不是两两配对。
  //
  // 这个结构也是"算客流要综合考虑"的基础：同一 cluster 的车站算一个整体。
  const STATION_CLUSTERS = { data: null, byStation: new Map(), sizeOf: new Map(),
                             group: null, colorOf: null, visible: true };

  // 某车站所属的站群信息（含按站群合计的规模）。车站可能由多个 station group 组成，
  // 命中任意一个即可。
  const stationClusterInfo = station => {
    const data = STATION_CLUSTERS.data;
    if (!data) return null;
    let entry = null;
    for (const group of relatedStations(station)) {
      const found = STATION_CLUSTERS.byStation.get(Number(group.entity_id));
      if (found) { entry = found; break; }
    }
    if (!entry) return null;
    const root = Number(entry.cluster);
    const memberCount = STATION_CLUSTERS.sizeOf.get(root) || 1;
    if (memberCount < 2) return { memberCount };
    const members = new Set((data.stations || [])
      .filter(item => Number(item.cluster) === root)
      .map(item => Number(item.entity_id)));
    // 把群里所有车站的线路并起来 —— 换乘是双向的，一条线停群里任何一个站都算这个群的服务
    const lineIds = new Set();
    (p.lines || []).forEach(line => {
      if ((line.stops || []).some(stop => members.has(Number(stop.station_group_id)))) {
        lineIds.add(line.entity_id);
      }
    });
    const entityByLine = new Map((p.lines || []).map(line => [line.entity_id, line]));
    const vehicleCount = (liveState?.vehicles || [])
      .filter(vehicle => entityByLine.has(vehicle.line) && lineIds.has(vehicle.line)).length;
    return { memberCount, lineCount: lineIds.size, vehicleCount };
  };

  // ---- 车站互通站群（整层加载）----
  layerTasks.push((async()=>{
    let manifest=null;
    try{
      const response=await fetch('/api/layers/stations/manifest',{cache:'no-store'});
      if(response.ok)manifest=await response.json();
    }catch(error){console.error(error);}
    if(!manifest||!manifest.data_file)return;
    let data=null;
    try{
      const response=await fetch(`/layers/${manifest.data_file}`,{cache:'no-store'});
      if(response.ok)data=await response.json();
    }catch(error){console.error(error);}
    if(!data||!Array.isArray(data.stations)||!data.stations.length)return;

    STATION_CLUSTERS.data=data;
    STATION_CLUSTERS.byStation=new Map(data.stations.map(item=>[Number(item.entity_id),item]));
    STATION_CLUSTERS.sizeOf=new Map((data.clusters||[]).map(item=>[Number(item.root),item.member_count]));

    // ⚠ 坐标系：本文件有两套，混用必然错位（已踩过）。
    //   · 挂在 mapLayer 里的层（地形 / 公路 / 产业 / 车辆 / 路网）用 **P() 底图坐标**，
    //     平移缩放交给 mapLayer 的 transform —— 会跟着地图动。
    //   · 挂在 svg 根的层（network-station-layer / depot-layer / live-layer）没有 transform，
    //     必须用 **screenPoint()** 算屏幕坐标，在 updateViewport() 里每帧重算。
    //   站群这一层只画连线（跟着地图缩放），不画圈。
    const group=S('g',{id:'network-station-cluster-layer','pointer-events':'none'});
    mapLayer.appendChild(group);
    STATION_CLUSTERS.group=group;

    // 站群配色：黄金角分布，相邻簇的色相拉得够开，便于区分
    const clusterColor=root=>`hsl(${((Number(root)||0)*137.508)%360} 58% 64%)`;
    STATION_CLUSTERS.colorOf=clusterColor;

    // ⛔ 互通虚线**不再画**（用户 2026-09-29：这些连线起不到作用）。
    //    ⚠️ 数据本身**要留着** —— 侧边栏的"站群"信息（几站互通、同群有哪些站）
    //    走 stationClusterInfo() → STATION_CLUSTERS.byStation / sizeOf，
    //    所以上面那几行登记不能删，只是不再画线。
    console.log(`[map] 站群图层：${data.counts.clusters} 群，其中 ${data.counts.linked_clusters} 片多站相连`,
      `最大一片 ${data.counts.largest_cluster} 站`, `互通 ${data.counts.links} 对`);
  })());

  // ---- 地形层（等高线 / 水深 / 地下站）----
  layerTasks.push((async()=>{
    let manifest=null;
    try{
      const response=await fetch('/api/layers/terrain/manifest',{cache:'no-store'});
      if(response.ok)manifest=await response.json();
    }catch(error){console.error(error);}
    if(!manifest||!manifest.grid||!manifest.data_file)return;
    let data=null;
    try{
      const response=await fetch(`/layers/${manifest.data_file}`,{cache:'no-store'});
      if(response.ok)data=await response.json();
    }catch(error){console.error(error);}
    if(!data||!Array.isArray(data.heights)||!data.heights.length)return;
    TERRAIN.grid=data.grid||manifest.grid;
    TERRAIN.heights=data.heights;
    TERRAIN.contourCache=null;
    TERRAIN.contourCacheKey=null;
    renderTerrain();
    const counts=manifest.counts||{};
    addOption(baseGroup,'等高线',{
      count:(counts.cols&&counts.rows)?`${counts.cols}×${counts.rows}`:null,
      title:'按官方四级画（base_config.gui.layers.contourLines）：主 100 m / 次 50 m 常显，'
        +'中间 10 m 只在视口 ≤4 km 时出现，细节 2 m 只在 ≤500 m 时出现（细则档按视口裁窗生成）',
      onChange:value=>{TERRAIN.visibleContours=value;renderContours();},
    });
    addOption(baseGroup,'海陆底色',{
      count:counts.water_points!=null?`${counts.water_points} 格水面`:null,
      title:'水按深度分档上蓝、陆按高度分档上灰，并描出 0 m 海岸线 —— 参照海图的分层设色',
      onChange:value=>{TERRAIN.visibleWater=value;renderWater();},
    });
    addOption(baseGroup,'地下站',{
      count:TERRAIN.undergroundCount??null,
      title:'站台高程低于同点地表 3 m 以上',
      onChange:value=>{TERRAIN.visibleUnderground=value;renderUnderground();},
    });
    console.log(`[map] 地形图层：${TERRAIN.grid.cols}×${TERRAIN.grid.rows} 网格`,
      `等高线 ${((TERRAIN.contourCache||{}).groups||[]).length} 条`,
      `水深 ${counts.water_points??'?'} 格`, `地下站 ${TERRAIN.undergroundCount??'?'}`);
  })());

  // 筛选自检：URL 上加 ?selftest=1 打开，结果打控制台。
  // 无头浏览器没法点按钮，靠这个复现"单独 / 叠加筛选"的行为并核对数量。
  // 挂在三个加载任务之后而不是靠 setTimeout —— 无头模式下虚拟时间不推进定时器。
  if(new URLSearchParams(window.location.search).get('selftest')==='1'){
    Promise.all(layerTasks).then(()=>{
      const count=selector=>[...document.querySelectorAll(selector)]
        .filter(node=>node.style.display!=='none').length;
      const snapshot=label=>console.log(
        `[selftest] ${label}｜车辆 ${count('#network-vehicles-layer [data-carrier]')}`);
      snapshot('初始（不限制）');
      onlyFilter('cargo',['PASSENGER']);snapshot('只看客运');
      onlyFilter('cargo',['FREIGHT']);snapshot('只看货运');
      clearFilters();onlyFilter('carrier',['RAIL']);snapshot('只看列车');
      onlyFilter('cargo',['FREIGHT']);snapshot('列车 + 货运（叠加）');
      clearFilters();snapshot('还原');
      console.log('[selftest] 完成');
    });
  }

  // ---- 车辆位置自动跟随 ----
  // 车辆是唯一会持续移动的图层：
  //   mod 每 15 个 update 重写 bridge/layer-vehicles.json
  //   → 服务端 watch() 检测到改动就自动重切分块（POST 到 ui/rail-map/layers/）
  //   → 但前端只在**首次加载**时 fetch 一次分块，之后从不重拉，
  //     所以页面上的车永远停在打开那一刻。这里补上"回看 → 变了就重画"。
  // 只做这一层：公路/产业/地形几乎不变，重载纯属浪费。
  // 两种显示状态都要照顾：放大时分块（reload），全图时概览骨架（refreshSummary）。
  // ⚠️ **默认关闭**（开关在侧边栏「交通工具 · 职能」组里）。用户 2026-09-29 定：
  //    车辆图层是快照，1296 个点里 1154 个是公路车，位置本来就变得慢；
  //    每 ~18 秒整层重切 + 重建上千个点，收益不值这个代价。要动态就自己勾。
  let vehiclesStamp=null;
  setInterval(()=>{
    if(!vehiclesAutoRefresh)return;                       // 默认关，勾了才刷新
    if(!vehiclesLayer||!vehiclesLayer.isVisible())return;
    fetch('/api/layers/vehicles/manifest',{cache:'no-store'})
      .then(response=>{if(!response.ok)throw new Error(`vehicles manifest: ${response.status}`);return response.json();})
      .then(manifest=>{
        const stamp=manifest.generated_at;
        if(stamp==null)return;
        if(vehiclesStamp==null){vehiclesStamp=stamp;return;}   // 首次只记基线
        if(stamp===vehiclesStamp)return;
        vehiclesStamp=stamp;
        if(vehiclesLayer.isSummary())vehiclesLayer.refreshSummary();
        else vehiclesLayer.reload();
      })
      .catch(()=>{});
  },5000);

  // ===== 对扩展文件开放的接口 ================================================
  // 站点结构（station-struct.js）与产业链流向（freight-flow.js）是**独立文件**，
  // 它们需要地图的坐标换算与绘图工具。这里只暴露最小必要集：只读工具 + 面板入口，
  // 不暴露内部可变状态，免得两边逻辑互相踩。
  // 就绪信号：window.dispatchEvent('tpf2map:ready') —— 扩展文件监听它即可，不要轮询。
  window.TPF2Map = {
    svg,
    mapLayer,
    S,                     // 建 SVG 元素：S(tag, attrs, text, parent)
    P,                     // 世界坐标 → 底图坐标（会跟着地图平移缩放）
    T,                     // 世界**向量 / 尺寸** → 底图尺寸（画范围框用这个）
    screenPoint,           // 世界坐标 → 屏幕坐标（固定屏幕尺寸的标记用这个）
    onViewport(callback){  // 注册每帧回调；注册时立刻先跑一次，避免首帧空白
      viewportHooks.push(callback);
      try{ callback(false); }catch(error){ console.error('[扩展图层]', error); }
    },
    worldPerMeter: ()=>baseScale,
    currentZoom: ()=>zoom,
    // 车站结构数据（layer-stations 整车版）。扩展文件直接读，不必自己再 fetch 一遍。
    stationData: ()=>STATION_CLUSTERS.data,
    // 图层面板：addGroup 让扩展**自建分组**（各占一块，别都挤进 facility）；
    // addOption 往指定分组里加条目。groups 是主文件自己那几个分组，供扩展复用。
    panel: { addOption, addGroup, groups: { base:baseGroup, net:netGroup, kind:kindGroup, cargo:cargoGroup, line:lineGroup, facility:facilityGroup } },
    // 统一取图层数据（manifest + data），省得每个扩展文件各写一遍 fetch 与容错
    async fetchLayer(name){
      const manifestResponse = await fetch(`/api/layers/${name}/manifest`, {cache:'no-store'});
      if(!manifestResponse.ok) throw new Error(`${name} manifest ${manifestResponse.status}`);
      const manifest = await manifestResponse.json();
      if(!manifest.data_file) return {manifest, data:null};
      const dataResponse = await fetch(`/layers/${manifest.data_file}`, {cache:'no-store'});
      if(!dataResponse.ok) throw new Error(`${name} data ${dataResponse.status}`);
      return {manifest, data: await dataResponse.json()};
    },
  };
  window.dispatchEvent(new CustomEvent('tpf2map:ready'));
};
