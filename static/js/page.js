// сортировщик таблицы
document.addEventListener('DOMContentLoaded', () => {
    const getSort = ({ target }) => {
        const order = (target.dataset.order = -(target.dataset.order || -1));
        const index = [...target.parentNode.cells].indexOf(target);
        const collator = new Intl.Collator(['en', 'ru'], { numeric: true });
        const comparator = (index, order) => (a, b) => order * collator.compare(
            a.children[index].innerHTML,
            b.children[index].innerHTML
        );
        // Приведем все числа к числовому формату
        // let all_floats = document.getElementsByTagName('td')
        let all_floats = $('#data-table td')
		for (let i = 0; i < all_floats.length; i++){
		    let number = all_floats[i].innerText
		    if (!number.match(/^\d\d\.\d\d\.\d\d\d\d/) && number.match(/^\d.*\d$/)){
		        all_floats[i].innerText = number.replace(/\s/, '').replace(/\s/, '')
                    .replace('\,', '.')
            }
		    // приведем датувремя к удобному для упорядочивания формату
		    if (number.match(/^\d\d\.\d\d.\d\d\d\d\s\d\d\:\d\d$/)){
		        all_floats[i].innerText = number.slice(6, 10) + number.slice(3, 5) + number.slice(0, 2)
                    + number.slice(11, 13) + number.slice(14)
            }
		}
        for(const tBody of target.closest('table').tBodies)
            tBody.append(...[...tBody.rows].sort(comparator(index, order)));

        for(const cell of target.parentNode.cells)
            cell.classList.toggle('sorted', cell === target);
        // вернем числа обратно к локализованному формату
        for (let i = 0; i < all_floats.length; i++) {
            let number = all_floats[i].innerText
            // Приведем датувремя обратно к локализованному формату
            if (number.match(/^\d{12}$/))
                all_floats[i].innerText = number.slice(6, 8) + '.' + number.slice(4, 6) + '.' +
                    number.slice(0, 4) + ' ' + number.slice(8, 10) + ':' + number.slice(10)
		    // if (!number.match(/^\d\d\.\d\d\.\d\d\d\d$/) && number.match(/^\d.*\d$/)){
		    //     if (number.match(/\./))
		    //         number = parseFloat(number).toLocaleString(undefined, {minimumFractionDigits: 2})
            //     else number = parseInt(number).toLocaleString()
		    //     all_floats[i].innerText = number
            // }

        }
    };
    document.querySelectorAll('.table_sort thead .col_sort').forEach(tableTH => tableTH
        .addEventListener('click', () => getSort(event)));

});


function send_form_with_param(name_param, value_param = ''){
    // Удалим параметр закачки файла
    $('[name="b_save_file"]').remove()
    // ДОбавим параметр
    let new_param = document.createElement('input')
    new_param.type = 'hidden'
    new_param.name = name_param
    new_param.value = value_param
    let form = document.getElementById('form')
    form.appendChild(new_param)
    form.submit()
}

function send_form_with_params(params){
    for (let park in params){
        let new_param = document.createElement('input')
        new_param.type = 'hidden'
        new_param.name = park
        new_param.value = params[park]
        let form = document.getElementById('form')
        form.appendChild(new_param)
    }
    form.submit()
}
