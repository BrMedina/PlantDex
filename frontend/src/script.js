
  const GREEN = '#4a7c3f';
  const INACTIVE = '#888';
 
  function setActive(el) {
    // Deactivate all items
    document.querySelectorAll('.nav-item').forEach(item => {
      item.classList.remove('active');
      item.querySelectorAll('.icon-stroke').forEach(s => s.setAttribute('stroke', INACTIVE));
      item.querySelectorAll('.icon-fill').forEach(s => s.setAttribute('fill', INACTIVE));
    });
 
    // Activate the clicked item
    el.classList.add('active');
    el.querySelectorAll('.icon-stroke').forEach(s => s.setAttribute('stroke', GREEN));
    el.querySelectorAll('.icon-fill').forEach(s => s.setAttribute('fill', GREEN));
  }
 
  function onFabClick() {
    // Add your FAB action here
    console.log('FAB tapped');
  }