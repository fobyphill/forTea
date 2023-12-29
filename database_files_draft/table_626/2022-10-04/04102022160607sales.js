$(document).ready(function () {

            var itemTable = $('#data-table').DataTable({
                responsive: true,
                paging: false,
                info: false,
                pageLength: 20,
                searching: false,
                ordering: false,
                autoWidth: false,
                language: {
                    "emptyTable": 'В этой категории нет товаров'
                },
                dom: '<"pull-left"f><"pull-right"l>tip',
                columnDefs: [
                    {
                        targets: [ 4 ],
                        render : function (data, type, row) {
                            return '<div class=number><span>'+Number(data).toFixed(2)+'</span></div>'
                        },
                    },
                ],
            });

            var cartTable = $('#cart-table').DataTable({
                responsive: true,
                paging: false,
                searching: false,
                ordering: false,
                autoWidth: false,
                info: false,
                language: {
                    "emptyTable": 'Пока товаров нет'
                },
            });

            $(document).on('change', '.sales-input', function (e){
                 let quantity = parseInt(this.value);
                 let id = this.id.slice(1)
                 if (quantity <= 0){
                     quantity = 1
                     this.value = quantity
                 }
                 let price = parseFloat(document.getElementById('p'+id).textContent)
                 let total = price * quantity
                 document.getElementById('t'+id).innerText = total.toFixed(2)
                 calc_cart();
                 let url = window.location.href
                 let searchParams = new URLSearchParams(url)
                 let page = searchParams.get('page')
                 if (page){
                     let page_input = document.createElement('input')
                     page_input.name = 'page'
                     page_input.value = page// добавили номер страницы
                     this.form.appendChild(page_input)
                 }
                 this.form.submit()
                 return false;
             });

            $('.addItem').click(function (e) {
                if (e.keyCode == 13){return false}
                let id = $(this).attr('data-id');
                let name = $(this).attr('data-name');
                //var stock = $(this).attr('data-stock');
                let price = $(this).attr('data-price');
                let new_item_in_cart = {}
                new_item_in_cart.id = parseInt(id)
                new_item_in_cart.name = name
                new_item_in_cart.price = parseFloat(price)
                new_item_in_cart.quantity = 1
                new_item_in_cart.total = parseFloat(price)
                let form = document.getElementById('form')
                let url = window.location.href
                let searchParams = new URLSearchParams(url)
                let page = searchParams.get('page')
                if (page){
                     let page_input = document.createElement('input')
                    page_input.name = 'page'
                    page_input.value = page
                    form.appendChild(page_input)
                }
                let cart_item = document.createElement('input')
                cart_item.name = 'cart_item_add'
                cart_item.value = JSON.stringify(new_item_in_cart)
                form.appendChild(cart_item) //добавили информацию о новом товаре в форму
                form.submit()
            });

            $(document).on('click', '.removeItem', function (e) {
                let id = this.id
                    //cartTable.row($(this).parents('tr')).data()[0];
                let form = document.getElementById('form')
                form.action = 'sales'
                let cart_item_del = document.createElement('input')
                cart_item_del.name = 'cart_item_del'
                cart_item_del.value = id.slice(1)
                form.appendChild(cart_item_del) // добавили ID удаленного товара
                let url = window.location.href
                let searchParams = new URLSearchParams(url)
                let page = searchParams.get('page')
                if (page){
                    let page_input = document.createElement('input')// добавили номер страницы
                    page_input.name = 'page'
                    page_input.value = page
                    form.appendChild(page_input)
                }
                let search_keyword = document.getElementById('search_keyword')
                form.submit()
            });
        });

//$(window).load(calc_cart());

window.onload = function () {
    //ширина выпадающих списков
    function set_width_tag_select(level_num){
        let cat_level = document.getElementsByName('cat'+level_num+'level')[0]
        let num = parseInt(cat_level.selectedIndex)
        let str_width =String(cat_level.options[num].text.length + 5) + 'ch'
        cat_level.style.width = str_width
    }
    set_width_tag_select(1)
    set_width_tag_select(2)
    set_width_tag_select(3)
    set_width_tag_select(4)

    calc_cart()
}

/*Функция обновления фильтров категорий*/
function cats_submit(this_select){
    let num_this_select = parseInt(this_select.name.slice(3,4))
    //отображение в списках
    if (num_this_select <= 3){
        let cat4 = document.getElementById('cat4level')
        cat4.children[0].selected = true
    }
    if (num_this_select <= 2){
        let cat3 = document.getElementById('cat3level')
        cat3.children[0].selected = true
    }
    if (num_this_select == 1){
        let cat2 = document.getElementById('cat2level')
        cat2.children[0].selected = true
    }
    let cart_items = document.getElementById('cart_items')
    document.getElementById('search_keyword').value = ''
    this_select.form.submit()
    }

/*Функция отправки данных при поиске*/
function search_submit(this_input) {
    let cart_items = document.getElementById('cart_items')
    this_input.form.appendChild(cart_items) //добавил информацию о корзине
    let search_keyword = document.getElementById('search_keyword')
    search_keyword.name = 'search_keyword'
    if (search_keyword.value.length > 0){
        this_input.form.appendChild(search_keyword)
    }
    this_input.form.submit()
}

function make_new_order(thisEl) {
    thisEl.form.action = 'order'
    thisEl.form.method = 'POST'
    thisEl.form.submit()
}

function  add_client(thisEl) {
    let form = document.getElementById('form')
    let tag_client = document.getElementById('client_id')
    tag_client.name = 'client_id' //добавили ID клиента
    let url = window.location.href
    let searchParams = new URLSearchParams(url)
    let page = searchParams.get('page')
    if (page){
         let page_input = document.createElement('input')
        page_input.name = 'page'
        page_input.value = page
        form.appendChild(page_input)
    }
    form.submit()
}

function calc_cart(){
        let itogo = 0;// Итоговая потребительская сумма
        let table_cart = document.getElementById('cart-table').children[1] // тело таблицы
        if (table_cart){
            for (let i = 0; i < table_cart.rows.length; i++){
                itogo += parseFloat(table_cart.children[i].children[4].children[0].textContent);
            }
            document.getElementById('itogo_table').children[0].children[0].children[1].innerHTML =
             "<h4><u>" + String(itogo) + "</u></h4>";
        }
        //проверка активности кнопки
        var button_order = document.getElementById('make_order')
        let client_id = document.getElementById('client_id')
        if (!table_cart || client_id){
            button_order.disabled=true
        }
         else {button_order.disabled=false}

         //Сбросим товары из корзины в поле в формате джейсон
        let array = []// объект для передачи в джейсон
        if (table_cart){  //Если столбиков в первой строке > 1, т.е. есть товары
            for (let i = 0; i < table_cart.rows.length; i++){
                let item = {}
                item.name = table_cart.children[i].children[1].innerText
                item.id = parseInt(table_cart.children[i].id)
                item.price = parseFloat(document.getElementById('p' + String(item.id)).innerText)
                item.quantity = parseInt(document.getElementById('q' + item.id).value)
                item.total = parseFloat(document.getElementById('t' + item.id).innerText)
                array.push(item)
            }
        }
        let cart_items = document.getElementById('cart_items')
        cart_items.value = JSON.stringify(array)
        return false;
    }

/*Нажатие энтера в поисковом поле*/
function press_enter_on_search(this_enter, evt){
    if (evt.key == 'Enter'){
        search_submit(this_enter)
    }
}

function press_enter_on_id_client(this_enter, evt){
    if (evt.key == 'Enter'){
        add_client(this_enter)
    }
}
